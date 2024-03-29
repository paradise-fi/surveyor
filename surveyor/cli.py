from surveyor import app
from surveyor.api import serializeSuiteResults
from surveyor.models import *
import click
from flask.cli import FlaskGroup
import os
import pwd
import sys
import json

class KeyVal(click.ParamType):
    name = "key=value"

    def convert(self, value, param, ctx):
        p = value.split("=", 2)
        if len(p) != 2:
            Self.fail(f"{value} is not a valid argument specification", param, ct)
        return p[0].strip(), p[1].strip()

def getUsername():
    return pwd.getpwuid(os.getuid())[ 0 ]

def validateCpuLimit(ctx, param, value):
    if value < 0:
        raise click.BadParameter("cpulimit needs to be positive")
    return value

def validateMemLimit(ctx, param, value):
    if value < 0:
        raise click.BadParameter("memlimit needs to be positive")
    return value

def validateTimeout(ctx, param, value):
    if value < 0:
        raise click.BadParameter("memlimit needs to be positive")
    return value

@click.command("createSuite")
@click.option("--dockerfile", type=click.File(), required=True,
    help="Dockerfile specifying the runtime environment")
@click.option("--param", "-p", type=KeyVal(), multiple=True,
    help="Docker ARGs passed to Dockerfile")
@click.option("--tasks", type=click.File(), required=True,
    help="JSON file specifying benchmarking tasks")
@click.option("--cpulimit", type=int, callback=validateCpuLimit, default=1,
    help="Set single task cpu cores limit")
@click.option("--ctimeout", type=int, callback=validateTimeout, default=3600,
    help="Set single task cpu timeout in seconds")
@click.option("--wtimeout", type=int, callback=validateTimeout, default=3600,
    help="Set single task wall clock timeout in seconds")
@click.option("--memlimit", type=int, callback=validateMemLimit, default=1024*1024*1024,
    help="Set single task memory limit (in bytes)")
@click.option("--description", "-d", type=str, required=True,
    help="Evaluation suite description")
@click.option("--run/--no-run", "-r", default=False)
def createSuite(dockerfile, param, tasks, cpulimit, memlimit, ctimeout, wtimeout,
                description, run):
    """
    Specify new evaluation suite and start evaluating it.
    """
    suite = BenchmarkSuite(author=getUsername(), description=description)
    suite.env = RuntimeEnv(
        dockerfile=dockerfile.read(),
        cpuTimeLimit=ctimeout,
        wallClockTimeLimit=wtimeout,
        cpuLimit=cpulimit,
        memoryLimit=memlimit)
    for key, value in param:
        suite.env.params.append(RuntimeParam(key=key, value=value))
    taskList = json.load(tasks)
    if not isinstance(taskList, list):
        raise RuntimeError(f"Task list is supposed to be JSON list, got {type(taskList)} instead")
    initialState = TaskState.pending if run else TaskState.created
    for t in taskList:
        if not isinstance(t, str):
            raise RuntimeError(f"Task is supposed to be string, got {type(t)} instead: '{t}'")
        suite.tasks.append(BenchmarkTask(command=t, state=initialState))
    db.session.add(suite)
    db.session.commit()

    print(f"Benchmarking suite registered with ID {suite.id}.")
    if run:
        print("Suite evaluation has started.")
    else:
        print(f"Suite evaluation was not started. You can start it via 'surveyor run --id {suite.id}")

@app.cli.command("runSuite")
@click.option("--id", "-i", type=int, required=True)
def runSuite():
    """
    Start evaluation of given suite
    """
    raise NotImplementedError("Not implemented yet")

@app.cli.command("results")
@click.option("--id", "-i", type=int, required=True)
def results(id):
    """
    Retrieve results for given task set
    """
    suite = db.session.query(BenchmarkSuite).get_or_404(id)
    json.dump(serializeSuiteResults(suite), sys.stdout, indent=4)

@click.group()
def cli():
    """Surveyor CLI interface"""
    pass

cli.add_command(createSuite)
cli.add_command(runSuite)
cli.add_command(results)

if __name__ == "__main__":
    cli()
