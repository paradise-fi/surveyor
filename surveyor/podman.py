import os
import signal
import json
import time
import subprocess
import contextlib
import dateutil.parser
import datetime
import dbus
from tempfile import TemporaryDirectory

# See https://github.com/containers/podman/issues/10173
CGROUP_WORKAROUND = True


proxy = dbus.SystemBus().get_object("org.freedesktop.systemd1", "/org/freedesktop/systemd1")
systemd = dbus.Interface(proxy, dbus_interface="org.freedesktop.systemd1.Manager")

class Cgroup:
    def __init__(self, path=None):
        self.path = path
        self.dummyProc = None

    def __str__(self):
        return f"<Cgroup {self.path}>"

    def occupy(self):
        """
        Add a dummy process to the group, so it does not die
        """
        self.dummyProc = subprocess.Popen(["sleep", "infinity"])
        self.addProcess(self.dummyProc.pid)

    def release(self):
        """
        Release the group - kill the dummy process and
        """
        if self.dummyProc is not None:
            self.dummyProc.kill()
            self.dummyProc.wait()

        os.rmdir(self.fsPath)

    @property
    def fsPath(self):
        return os.path.join("/sys/fs/cgroup/", self.path[1:])

    def addProcess(self, pid):
        """
        Add a process to the group
        """
        with open(os.path.join(self.fsPath, "cgroup.procs"), "w") as f:
            f.write(str(pid) + "\n")

    def enableControllers(self, controllers):
        with open(os.path.join(self.fsPath, "cgroup.subtree_control"), "w") as f:
            f.write(" ".join([f"+{x}" for x in controllers]))

    @staticmethod
    def createScope(scopeName):
        """
        Use systemd to create a new user cgroup scope. Put the current process
        into it under subgroup 'manager' (when the process is directly in the
        scope, you cannot set cgroup.subtree_control). Return Cgroup object of
        the scope.
        """
        # Inspiration: https://unix.stackexchange.com/questions/525740/how-do-i-create-a-systemd-scope-for-an-already-existing-process-from-the-command
        command = ["busctl", "call", "--user",
            "org.freedesktop.systemd1", "/org/freedesktop/systemd1",
            "org.freedesktop.systemd1.Manager", "StartTransientUnit",
            "ssa(sv)a(sa(sv))", scopeName + ".scope",
            "fail", "4", "PIDs", "au", "1",
            str(os.getpid()), "Delegate", "b", "1",
            "MemoryAccounting", "b", "1", "CPUAccounting", "b", "1",
            "0"]
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if p.returncode != 0:
            raise RuntimeError(p.stdout.decode("utf-8"))

        with open(f"/proc/{os.getpid()}/cgroup") as f:
            path = f.read().split("::")[1].strip()
        cgroup = Cgroup(path)

        managerPath = os.path.join(cgroup.path, "manager")
        managerDirPath = os.path.join(cgroup.fsPath, "manager")
        os.mkdir(managerDirPath)
        managerGroup = Cgroup(path=managerPath)
        managerGroup.addProcess(os.getpid())
        return cgroup

    @contextlib.contextmanager
    def newGroup(self, name, controllers=["cpu", "memory", "io"]):
        """
        Context manager for creating new sub-groups.
        """
        groupPath = os.path.join(self.path, name)
        dirPath = os.path.join(self.fsPath, name)
        os.mkdir(dirPath)
        group = Cgroup(path=groupPath)
        try:
            yield group
        finally:
            group.release()

    def _readGroupfile(self, filename):
        with open(os.path.join(self.fsPath, filename)) as f:
            lines = f.readlines()
        d = {}
        for l in lines:
            s = [x.strip() for x in l.split()]
            d[s[0]] = s[1]
        return d

    def cpuStats(self):
        s = self._readGroupfile("cpu.stat")
        return {k: int(v) for k, v in s.items()}

    def memoryStats(self):
        s = self._readGroupfile("memory.stat")
        return {k: int(v) for k, v in s.items()}

class PodmanError(RuntimeError):
    def __init__(self, message, log):
        super().__init__(message)
        self.log = log

def invokePodmanCommand(command, **kwargs):
    command = ["podman", "--cgroup-manager", "cgroupfs"] + command
    if "inspect" not in command:
        print(command)
    # command = ["podman"] + command
    p = subprocess.run(command,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    output = p.stdout.decode("utf-8")
    if p.returncode != 0:
        raise PodmanError(f"{' '.join(command)}", output)
    return output

def imageExists(name):
    """
    Return if given image exists
    """
    p = subprocess.run(["podman", "image", "exists", name],
        capture_output=True)
    return p.returncode == 0

def containerExists(name):
    p = subprocess.run(["podman", "container", "exists", name],
        capture_output=True)
    return p.returncode == 0

def buildImage(dockerfile, tag, args, cpuLimit=None, memLimit=None):
    """
    Build image for given dockerfile (string). Return the logs of the build.
    """
    with TemporaryDirectory() as d:
        dockerfilePath = os.path.join(d, "Dockerfile")
        with open(dockerfilePath, "w") as f:
            f.write(dockerfile)
        command = ["build", "-t", tag]
        for k, v in args.items():
            command.extend(["--build-arg", f"{k}={v}"])
        if memLimit is not None:
            command.extend(["--memory", str(memLimit)])
        if cpuLimit is not None:
            command.extend(["--cpu-period", "100000"])
            command.extend(["--cpu-quota", str(100000 * cpuLimit)])
        command.extend(["-f", dockerfilePath])
        command.append(d)

        return invokePodmanCommand(command)

def createContainer(image, command, mounts=[], cpuLimit=None, memLimit=None,
                    cgroup=None, name=None):
    """
    Create container, return its identifier
    """
    podmanCmd = ["container", "create", "--runtime", "crun"]
    for m in mounts:
        podmanCmd.extend(["--mount", f"type=bind,src={m['source']},target={m['target']}"])
    if cpuLimit is not None:
        podmanCmd.extend(["--cpus", str(cpuLimit)])
    if memLimit is not None:
        podmanCmd.extend(["--memory", str(memLimit)])
        podmanCmd.extend(["--memory-swap", str(memLimit)])
    if cgroup is not None:
        podmanCmd.extend(["--cgroup-parent", cgroup.path])
    if name is not None:
        podmanCmd.extend(["--name", name])

    podmanCmd.append(image)
    podmanCmd.extend(command)

    if CGROUP_WORKAROUND:
        r, w = os.pipe()
        pid = os.fork()
        if pid > 0:
            print(f"Parent: {os.getpid()}")
            os.close(w)
            with os.fdopen(r) as r:
                os.waitpid(pid, 0)
                s = r.read()
                return s.strip()
        else:
            os.close(r)
            cgroup.addProcess(pid)
            with os.fdopen(w, 'w') as w:
                res = invokePodmanCommand(podmanCmd)
                w.write(res)
                w.close()
                os._exit(0)
    else:
        return invokePodmanCommand(podmanCmd).strip()

def inspectContainer(container):
    command = ["inspect", container]
    return json.loads(invokePodmanCommand(command))[0]

def containerRunTime(inspection):
    """
    Return container runtime in microseconds
    """
    started = dateutil.parser.parse(inspection["State"]["StartedAt"])
    finished = dateutil.parser.parse(inspection["State"]["FinishedAt"])
    if datetime.datetime.timestamp(finished) < 0:
        finished = datetime.datetime.now(datetime.timezone.utc)
    delta = finished - started
    return delta.seconds * 1000000 + delta.microseconds

def containerStatus(inspection):
    return inspection["State"]["Status"]

def containerExitCode(inspection):
    return inspection["State"]["ExitCode"]

def containerOomKilled(inspection):
    return inspection["State"]["OOMKilled"]

def containerCgroup(inspection):
    name = inspection["HostConfig"]["CgroupParent"]
    return Cgroup(path=name)

def stopContainer(container, timeout=None):
    command = ["stop", container]
    if timeout is not None:
        command.extend(["--timeout", str(timeout)])
    return invokePodmanCommand(command)

def removeContainer(container):
    command = ["container", "rm", "-f", container]
    return invokePodmanCommand(command)

def containerLogs(container):
    command = ["logs", container]
    return invokePodmanCommand(command)

def runAndWatch(container, cgroup, notify=None, wallClockLimit=None,
            cpuClockLimit=None, pollInterval=1, notifyInterval=10):
    """
    Run a container and watch it for time limits. Returns a dictionary with
    container statistics.
    """
    inspection = inspectContainer(container)

    command = ["container", "start", "--runtime", "crun", container]
    if CGROUP_WORKAROUND:
        pid = os.fork()
        if pid > 0:
            os.waitpid(pid, 0)
        else:
            cgroup.addProcess(pid)
            invokePodmanCommand(command)
            os._exit(0)
    else:
        invokePodmanCommand(command)
    print("Container started")

    timeout = False
    ticks = 0
    while True:
        time.sleep(pollInterval)
        ticks += 1
        if ticks % notifyInterval == 0 and notify is not None:
            notify()
        inspection = inspectContainer(container)
        if containerStatus(inspection) != "running":
            break
        wTime = containerRunTime(inspection)
        cTime = cgroup.cpuStats()["usage_usec"]
        if wTime >= wallClockLimit * 1000000 or cTime >= cpuClockLimit * 1000000:
            stopContainer(container, timeout=1)
            timeout = True
    print("Container terminated")

    inspection = inspectContainer(container)
    print("Before stats")
    stats = {
        "cpuStat": cgroup.cpuStats(),
        "memStat": cgroup.memoryStats(),
        "wallTime": containerRunTime(inspection),
        "exitCode": containerExitCode(inspection),
        "outOfMemory": containerOomKilled(inspection),
        "timeout": timeout,
        "output": containerLogs(container)
    }
    print(stats)
    print("After stats")
    return stats



