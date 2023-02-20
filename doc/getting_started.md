# Getting started with Surveyor

Surveyor allows you to easily run large number of benchmarks in a well-defined
environment leveraging your computational resources. You just specify the tasks
and Surveyor takes care of the rest:

- building the runtime environment on the runners,
- distributing the benchmarking tasks between multiple computers.
- It also isolates the processes running a on single computer, so they do not
  affect each other.
- It allows you to precisely specify resource limits (wall-clock time, cpu-time,
  memory) and monitor resource usage.
- Lastly, it collects benchmarking statistics to a central place where you can
  easily extract it and process it.

# Basic concepts

- **Runtime environment** is the environment in which the individual tasks run.
  The environment is specified as a [Docker
  image](https://searchitoperations.techtarget.com/definition/Docker-image).
  This allows you to install arbitrary dependencies and provide the exactly same environment across various computers.

- **Benchmarking task** is a single command (string) executed in a runtime
  environment. This task is responsible for executing the actual result and possibly recording additional statistics about the run (e.g., number of explored states or progress over time).

- **Benchmarking suite** is a collection of an environment and a list of tasks.

Therefore, if you want to benchmark your program, you have to prepare:
- a [`Dockerfile`](https://docs.docker.com/engine/reference/builder/) specifying
  the environment. Install your dependencies, pull your program and build it in
  there. Note that the container has to be self-contained - it cannot reference
  any local files (as there are no such files on the computers running the
  tasks). Your Dockerfile can receive environmental parameter - these parameters
  can be, e.g., used to specify a particular Git revision of your software.
- Prepare a list of tasks. You specify them to Surveyor as a JSON list of
  strings (see example below). You will probably wrap your actual tasks into a
  helper scripts, that will encode the output of your tasks into a format that
  Surveyor expects (see below).
- Then you just submit these to Surveyor. It will execute them all.
- Finally, you can download a JSON with the task results and use it as an input
  into your report generator.

# Hands-on: creating a simple benchmarking task

Let's walk your through a process of creating a benchmarking task. We won't do
anything sophisticated nor useful: it will be just a toy example. We will try to
run scripts in `doc/examples/resources` inside Surveyor.

First, we have to define a runtime environment. So let's write a
[`example1.Dockerfile`](doc/examples/example1.Dockerfile):

```.Dockerfile
# We will use an Ubuntu base image from a repository
FROM ubuntu:20.04

# Let's install our dependencies - in our case, it will be the program stress
# and git. We also install apt-transport-https and ca-certificates so we can use
# SSL to do `git pull`
RUN export DEBIAN_FRONTEND="noninteractive" && apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates apt-transport-https \
      stress git && \
      rm -rf /var/lib/apt/lists/*

# Create a directory where we store our scripts
RUN mkdir -p /scripts

# Fetch the scripts from Surveyor and place them under /scripts. Surveoyr
# provides several simple testing scripts in its repository.
#
# Note that if you use a compiled program, you would probably fetch the sources,
# compile it and install it.
RUN cd /tmp; \
    git clone https://github.com/paradise-fi/surveyor; \
    cp surveyor/doc/examples/resources/* /scripts

# Update PATH so we can call our scripts as installed programs
ENV PATH="/scripts:${PATH}"
```

To test the environment, you don't have to upload it to Surveyor. You can test
it locally - you just need a [Docker](https://www.docker.com/) or
[Podman](https://podman.io/) installed on your machine. Then your can:

```.sh
# Build the image
docker build . doc/examples/example1.Dockerfile -t "example1"
# Test the image - open a shell inside the container
docker run -it example1 /bin/bash
# Note that if you use podman, just replace 'docker' with 'podman'
```

Ok, so this is the runtime environment. What about the tasks? We will:
- `countdown.sh` to 10,
- `useCpu` on 2 threads for 10 seconds and
- `useMemory` with 512MB or RAM.

To specify it we create
[`example1.tasks.json`](doc/examples/example1.tasks.json):

```.js
[
    "countdown.sh 10",
    "useCpu.sh 10 2",
    "useMemory.sh 10 512M"
]
```

Finally, it is time to run our first benchmarks! You can create the benchmarking
task via a web interface or via CLI. On the web you just fill in the form. Using
CLI, you just need to invoke the following command:

```
$ surveyor createSuite \
    --dockerfile example1.Dockerfile \
    --tasks example1.tasks.json \
    --description "First surveyor test" \
    --cpulimit 1 \ # Use only 1 core
    --wtimeout 20 \ # Do not run longer than 20 seconds
    --ctimeout 20 \ # Do not use more than 20 seconds of CPU time
    --memlimit 1073741824 \ # Do not use more than 1 GB or RAM
    --run # Start the evaluation
Benchmarking suite registered with ID 102.
Suite evaluation has started.
```

When your submit it, you can see the progress. Currently, only via a web. The
CLI has not been implemented for that yet. You can see that all tasks have
succeeded and you can download their artifacts.

Now, try to execute the same task list, but limit the number of memory or cpu
time. You will see that these benchmarks will fail.

# Formal requirements for the tasks

In the previous text, we often referred to "artifact" but we haven't explained
it. Let's fix it.

Generally speaking, task is just a command you can execute inside the
environment. Surveyor will take care of limiting and monitoring the used
resources (time and memory). However, this might not always be sufficient - you
might be interested in collecting more detailed statistics - e.g., if a solution
was found, how many states have been explored, etc. For this, the task can save
a JSON file into `/artefact/results.json`. This file will be post-mortem
extracted and saved with the task result into the database.

To sum it up:

- The task is required to perform the work. If the benchmark was successful
  (i.e., not fatal error occurred) it should have ended with return value 0.
- Return value other than 0 should be used to indicate a fatal failure.
- If you need to mark if your program solved a benchmark, we advise you to store
  this into the artefact.
- The task can save `/artefact/results.json` to store an arbitrary,
  benchmark-defined information. The value is extracted after stopping it.

