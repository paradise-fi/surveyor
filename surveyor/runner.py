import click
import os
import multiprocessing
import time
import hashlib
import shlex
import json
import logging
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from threading import Thread, Lock, RLock, Condition
from flask_sqlalchemy import SignallingSession
from surveyor import app, db
from surveyor.models import BenchmarkTask
from surveyor.common import withCleanup, asFuture
from surveyor import podman
from surveyor.podman import Cgroup

def installedPhysicalMemory():
    return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')

class NotEnoughResources(RuntimeError):
    pass

class EnvironmentBuildError(RuntimeError):
    pass

class TaskRunError(RuntimeError):
    pass

class ArtefactError(RuntimeError):
    pass

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
    def __init__(self):
        self.mutex = RLock()
        self.buildInProgress = {} # env.id -> mutex
        self.builder = ThreadPoolExecutor(max_workers=3)

    def __enter__(self):
        return self.builder.__enter__()

    def __exit__(self, *args, **kwargs):
        return self.builder.__exit__(*args, **kwargs)

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
        return podman.imageExists(f"localhost/{envName}")

    def _buildContainer(self, env):
        """
        Build container for the given environment. Return container name and
        notify about completion via Condition.
        """
        envName = self._envName(env)
        try:
            buildLog = podman.buildImage(dockerfile=env.dockerfile, tag=envName,
                args={x.key: x.value for x in env.params},
                cpuLimit=env.cpuLimit, memLimit=env.memoryLimit,
                noCache=True) # Force rebuilding the container when it downloads external dependencies
            logging.info(buildLog)
        except podman.PodmanError as e:
            raise EnvironmentBuildError(
                f"Build of environment {env.id} has failed with:\n{e.log}\n\n{e}")
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
            return self.getImage(env)
        logging.info(f"Environment {env.id} not available, building it")
        return self.builder.submit(lambda: self._buildContainer(env))


@contextmanager
def localDbSession():
    session = db.create_scoped_session()
    try:
        yield session
    finally:
        session.remove()

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

def extractArtefact(path):
    """
    Extracts benchmark artefact from the path.
    """
    try:
        with open(os.path.join(path, "results.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        raise ArtefactError("No artefact file found")
    except json.JSONDecodeError as e:
        with open(os.path.join(path, "results.json")) as f:
            raise ArtefactError(f"Ivanlid syntax: {e}.\n\nSource file:\n{f.read()}")
    except Exception as e:
        with open(os.path.join(path, "results.json"), "rb") as f:
            raise ArtefactError(f"Artefact error: {e}.\n\nSource file:\n{f.read()}")

def createContainerName(task):
    containerName = f"surveyor-task-{task.id}"
    if podman.containerExists(containerName):
        # There is a dangling container...
        suffix = 1
        while podman.containerExists(f"{containerName}-{suffix}"):
            suffix += 1
        containerName = f"{containerName}-{suffix}"
    return containerName

def executeTask(task, imageName, parentCgroup):
    """
    Given a benchmarking task, run it in given container. Updates "updatedAt"
    field on the model and stores benchmarking results to the model.
    """
    dbSession = SignallingSession.object_session(task)
    with TemporaryDirectory() as d, parentCgroup.newGroup(f"task{task.id}") as cgroup:
        logging.info(f"Starting container for task {task.id}")
        # Create a separate cgroup in case OOM killer starts working
        with cgroup.newGroup("benchmark", controllers=[]) as containerCgroup:
            env = task.suite.env
            buildOutput = "" if task.output is None else task.output
            container = None
            try:
                container = podman.createContainer(
                    image=imageName, command=shlex.split(task.command),
                    mounts=[{
                        "target": "/artefact",
                        "source": d
                    }],
                    cpuLimit=env.cpuLimit, memLimit=env.memoryLimit,
                    cgroup=containerCgroup, name=createContainerName(task))
                logging.debug(f"Container created for task {task.id}")
                def notify():
                    task.poke(podman.containerLogs(container))
                    dbSession.commit()
                stats = podman.runAndWatch(
                    container, containerCgroup, cgroup, notify,
                    env.wallClockTimeLimit, env.cpuTimeLimit)
            except podman.PodmanError as e:
                logging.error(f"Cannot execute task {task.id}: {e.log} \n\nCommand: {e}")
                raise TaskRunError(f"Cannot execute task: {e.log} \n\nCommand: {e}")
            finally:
                if container is not None:
                    podman.removeContainer(container)

        exitcode = stats["exitCode"]
        dbStats = {
            "cpuTime": stats["cpuStat"]["usage_usec"],
            "wallTime": stats["wallTime"],
            "userTime": stats["cpuStat"]["user_usec"],
            "systemTime": stats["cpuStat"]["system_usec"],
            "outOfMemory": stats["outOfMemory"],
            "timeout": stats["timeout"],
            "memStat": stats["memStat"],
            "memUsage": stats["maxMemory"],
            "artefactError": None
        }
        try:
            artefact = extractArtefact(d)
        except ArtefactError as e:
            dbStats["artefactError"] = str(e)
            artefact = None

        task.finish(exitcode, stats["output"], dbStats, artefact)
        dbSession.commit()

def evaluateTask(taskId, envManager, cgroup):
    """
    Given a BenchmarkTask id evaluate it.
    """
    with localDbSession() as dbSession:
        try:
            task = dbSession.query(BenchmarkTask).get(taskId)
            envImage = obtainEnvironment(task, envManager)
            executeTask(task, envImage, cgroup)
            dbSession.commit()
        except (EnvironmentBuildError, TaskRunError) as e:
            task.finish(1, str(e), None, None)
        except Exception as e:
            task.abandon()
            raise e
        finally:
            logging.info(f"Task {taskId} finished")
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
@click.option("--scope/--no-scope", default="--scope",
    help="Create dedicated scope or use scope/unit from systemd")
def run(cpulimit, memlimit, joblimit, id, scope):
    """
    Run executor daemon
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

    if scope:
        cgroup = Cgroup.createScope("surveyor_runner")
    else:
        cgroup = Cgroup.processGroup()
        cgroup.moveIntoSubgroup("manager")
    cgroup.enableControllers(["cpu", "memory", "io"])

    resources = ResourceManager(job=joblimit, cpu=cpulimit, mem=memlimit)
    envManager = EnvironmentManager()
    with envManager:
        logging.info(f"Runner on {id} started")
        while True:
            if resources.availableResources["job"] == 0:
                time.sleep(1)
                continue
            task = BenchmarkTask.fetchNew(
                resources.availableResources["cpu"],
                resources.availableResources["mem"])
            if task is None:
                db.session.commit()
                time.sleep(1)
                continue
            logging.info(f"Fetched new task for evaluation {task.id}")
            try:
                task.acquire(id)
                logging.info(f"Task {task.id} acquired")
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
                    args=[task.id, envManager, cgroup])
                t.start()
            except:
                logging.error(f"Abandoning task {task.id}")
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
