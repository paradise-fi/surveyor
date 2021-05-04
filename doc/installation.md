# Installation

Surveyor is a Python application (written in Flask). Therefore, to run it, you
will need Python 3. If you install it via `setup.py` all the dependencies should
be installed automatically.

On top of that, Surveyor requires a podman installation and a system with
Cgroups v2. The podman installation has to contain commit
[`17ce567c6827abdcd517699bc07e82ccf48f7619`](https://github.com/containers/podman/commit/17ce567c6827abdcd517699bc07e82ccf48f7619).
At the time of writing, it means that you need to compile Podman yourself.