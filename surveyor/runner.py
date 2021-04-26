import click
import os
import multiprocessing
import time
import types
import hashlib
import io
import shlex
import json
import subprocess
import dateutil.parser
from pathlib import Path
from subprocess import Popen, TimeoutExpired, PIPE
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from threading import Thread, Lock, RLock, Condition
from datetime import datetime
from flask_sqlalchemy import SignallingSession
from podman import PodmanClient
from podman.errors import BuildError, APIError
from urllib3.exceptions import ReadTimeoutError
from surveyor import app, db
from surveyor.models import BenchmarkTask
from surveyor.common import withCleanup, asFuture

def installedPhysicalMemory():
    return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')

class NotEnoughResources(RuntimeError):
    pass

class EnvironmentBuildError(RuntimeError):
    pass

@contextmanager
def podmanApiEndpoint():
    """
    Run podman API endpoint process as a context
    """
    with TemporaryDirectory() as d:
        socket = os.path.join(d, "podman.sock")
        try:
            proc = Popen(["podman", "system", "service", "-t0", "unix://" + socket],
                stdout=PIPE, stderr=PIPE)
            # We have no way to find out if the process failed after we yield,
            # so wait a second to find if it was executed correctly or not.
            stdout, stderr = proc.communicate(timeout=1)
            # If we get here, something is wrong; raise exception
            RuntimeError(f"Cannot start podman API process: {stdout}\n{stderr}")
        except OSError as e:
            RuntimeError(f"Cannot start podman API process - do you have podman "
                         f" installed?\n\n {e}")
        except TimeoutExpired:
            # Podman process is running!
            yield socket
        finally:
            proc.kill()

class ResourceManager:
    def __init__(self, **kwargs):
        self.availableResources = kwargs
        self.loans = {}
        self.mutex = Lock()

    @contextmanager
    def capture(self, **kwargs):
        """
        Capture resources, return resource
        """
        loan = kwargs
        with self.mutex:
            for r, v in loan.items():
                if self.availableResources[r] < v:
                    raise NotEnoughResources(r)
                self.availableResources[r] -= v
        try:
            yield loan
        finally:
            with self.mutex:
                for r, v in loan.items():
                    self.availableResources[r] += v

class EnvironmentManager:
    def __init__(self, podmansocket):
        self.client = PodmanClient("unix://" + podmansocket)
        self.mutex = RLock()
        self.buildInProgress = {} # env.id -> mutex
        self.builder = ThreadPoolExecutor(max_workers=3)

    def __enter__(self):
        return self.builder.__enter__()

    def __exit__(self, *args, **kwargs):
        return self.builder.__exit__(*args, **kwargs)

    def printPodmanInfo(self):
        version = self.client.version()
        print("Release: ", version["Version"])
        print("Compatible API: ", version["ApiVersion"])
        print("Podman API: ", version["Components"][0]["Details"]["APIVersion"], "\n")

    @staticmethod
    def _envName(env):
        """
        Return image name for given environment.
        """
        # We use database ID + 8 character prefix from Dockerfile hash in order
        # to prevent situations when database changes and local images are
        # cached
        m = hashlib.sha256()
        m.update(env.dockerfile.encode(encoding="UTF-8"))
        return f"surveyor-env-{env.id}-{m.hexdigest()[:8]}"

    def _isEnvAvailable(self, envName):
        return self.client.images.exists(f"localhost/{envName}")

    def _buildContainer(self, env):
        """
        Build container for the given environment. Return container name and
        notify about completion via Condition.
        """
        envName = self._envName(env)
        try:
            _, buildLog = self.client.images.build(
                fileobj=io.StringIO(env.dockerfile),
                tag=envName,
                timeout=3600,
                buildargs={x.key: x.value for x in env.params}
                # TBA: Container build limits
            )
        except (BuildError, APIError, TypeError) as e:
            raise EnvironmentBuildError(
                f"Build of environment {env.id} ({env.description}) has failed with: {e}")
        finally:
            with self.mutex:
                condition = self.buildInProgress[env.id]
                del self.buildInProgress[env.id]
                with condition:
                    condition.notify_all()
        return envName

    def getImage(self, env):
        """
        Return image name of an container for given BenchmarkEnvironment. The
        name is wrapped into a future as the container might be build. If
        corresponding container is not found, it is built. If the container
        cannot be built, raises EnvironmentBuildError via the future.
        """
        envName = self._envName(env)
        buildInProgress = False
        with self.mutex:
            if self._isEnvAvailable(envName):
                return asFuture(envName)
            if env.id in self.buildInProgress:
                conditionVariable = self.buildInProgress[env.id]
                buildInProgress = True
            else:
                conditionVariable = Condition()
                self.buildInProgress[env.id] = conditionVariable
        if buildInProgress:
            with conditionVariable:
                conditionVariable.wait()
            # Note that build might have failed
            if self._isEnvAvailable(envName):
                return asFuture(envName)
            return self.getImage(self, env)
        return self.builder.submit(lambda: self._buildContainer(env))


@contextmanager
def localDbSession():
    session = db.create_scoped_session()
    try:
        yield session
    finally:
        session.remove()

def inspectContainer(container):
    """
    Return a dictionary of container inspection result. This is a substition for
    the missing functionality in podman-py.
    """
    command = ["podman", "container", "inspect", "--format", "json", container.name]
    res = subprocess.run(command, capture_output=True, check=True)
    return json.loads(res.stdout)[0]

def containerRunTime(inspection):
    """
    Return container runtime in microseconds
    """
    started = dateutil.parser.parse(inspection["State"]["StartedAt"])
    finished = dateutil.parser.parse(inspection["State"]["FinishedAt"])
    delta = finished - started
    return delta.seconds * 1000000 + delta.microseconds


def obtainEnvironment(task, envManager):
    """
    Return an image name for running given task. If needed, build one.
    """
    dbSession = SignallingSession.object_session(task)
    envImageF = envManager.getImage(task.suite.env)
    while not envImageF.done():
        try:
            return envImageF.result(timeout=20)
        except TimeoutError:
            task.poke(None)
            dbSession.commit()
    return envImageF.result()

def containerOutput(container):
    """
    Return container stdout and stderr as string
    """
    lines = [x.decode("utf-8") for x in container.logs(stdout=True, stderr=True)]
    return "\n".join(lines)

def extractArtefact(path):
    """
    Extracts benchmark artefact from the path.
    """
    try:
        with open(os.path.join(path, "results.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def executeTask(task, imageName, podmanEnd):
    """
    Given a benchmarking task, run it in given container. Updates "updatedAt"
    field on the model and stores benchmarking results to the model.
    """
    dbSession = SignallingSession.object_session(task)
    with PodmanClient("unix://" + podmanEnd) as client, TemporaryDirectory() as d:
        print("Starting container...")
        buildOutput = "" if task.output is None else task.output
        container = client.containers.create(
            image=imageName, command=shlex.split(task.command),
            mounts=[{
                "type": "bind",
                "target": "/artefact",
                "source": d
                # TBA resource limits
            }])
        container.start()

        running = True
        while running:
            try:
                y = container.wait(timeout=5)
                running = False
            except ReadTimeoutError:
                output = containerOutput(container)
                print("Current output: " + output)
                task.poke(buildOutput + output)
                dbSession.commit()

        output = buildOutput + containerOutput(container)
        inspection = inspectContainer(container)
        exitcode = inspection["State"]["ExitCode"]
        runtime = containerRunTime(inspection)
        stats = {
            "oomKilled": inspection["State"]["OOMKilled"]
        }
        result = extractArtefact(d)

        task.finish(exitcode, output, runtime, stats, result)
        dbSession.commit()

def evaluateTask(taskId, envManager, podmanEndpoint):
    """
    Given a BenchmarkTask id evaluate it.
    """
    with localDbSession() as dbSession:
        try:
            task = dbSession.query(BenchmarkTask).get(taskId)
            envImage = obtainEnvironment(task, envManager)
            executeTask(task, envImage, podmanEndpoint)
            dbSession.commit()
        except EnvironmentBuildError as e:
            task.finish(1, str(e), None, None, None)
        except Exception as e:
            task.abandon()
            raise e
        finally:
            print(f"Task {taskId} finished")
            dbSession.commit()

@app.cli.command("run")
@click.option("--cpulimit", "-c", type=int, default=multiprocessing.cpu_count() - 1,
    help="Limit number of CPU cores used by the runner")
@click.option("--memlimit", "-m", type=int, default=installedPhysicalMemory(),
    help="Limit number of memory used by the runner")
@click.option("--joblimit", "-j", type=int, default=multiprocessing.cpu_count() - 1,
    help="Limit number of parallely executed tasks")
@click.option("--id", "-i", type=str, default=os.uname().nodename,
    help="Identification of the runner")
def run(cpulimit, memlimit, joblimit, id):
    """
    Run executor daemon
    """
    with podmanApiEndpoint() as podmanEndpoint:
        resources = ResourceManager(job=joblimit, cpu=cpulimit, mem=memlimit)
        envManager = EnvironmentManager(podmanEndpoint)
        with envManager:
            while True:
                if resources.availableResources["job"] == 0:
                    time.sleep(1)
                    continue
                task = BenchmarkTask.fetchNew(
                    resources.availableResources["cpu"],
                    resources.availableResources["mem"])
                if task is None:
                    db.session.commit()
                    print(f"No tasks available, sleeping")
                    time.sleep(1)
                    continue
                print(f"Fetched new task {task.id}")
                try:
                    task.acquire(id)
                    print(f"Task {task.id} acquired")
                    db.session.commit()
                except:
                    db.session.rollback()
                    raise
                try:
                    env = task.suite.env
                    resourcesHandle = resources.capture(
                        cpu=env.cpuLimit, mem=env.memoryLimit, job=1)
                    resourcesHandle.__enter__()
                    t = Thread(
                        target=withCleanup(evaluateTask, resourcesHandle.__exit__),
                        args=[task.id, envManager, podmanEndpoint])
                    t.start()
                except:
                    task.abandon()
                    db.session.commit()
                    resourcesHandle.__exit__(*sys.exc_info())
                    raise

@app.cli.command("gc")
def gc():
    """
    Garbage collect old runtime environments
    """
    # TBA
    pass

@click.group()
def cli():
    """Runner CLI interface"""
    pass

cli.add_command(run)
cli.add_command(gc)

if __name__ == "__main__":
    cli()