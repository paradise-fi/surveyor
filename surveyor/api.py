from surveyor import app, db
from surveyor.models import *

def serializeSuiteOverview(suite):
    return {
        "id": suite.id,
        "created": suite.created,
        "author": suite.author,
        "taskCount": len(suite.tasks),
        "completedTaskCount": suite.completedTaskCount(),
        "assignedTaskCount": suite.assignedTaskCount(),
        "description": suite.env.description # TBA migrate the field
    }

def serializeSuiteDetail(suite):
    s = serializeSuiteOverview(suite)
    s["env"] = serializeEnv(suite.env)
    s["tasks"] = [serializeTask(x) for x in suite.tasks]
    return s

def serializeSuiteResults(suite):
    return {
        "id": suite.id,
        "description": suite.env.description, # TBA migrate the field
        "tasks": [serializeTaskResult(x) for x in suite.tasks]
    }

def serializeTask(task):
    return {
        "id": task.id,
        "command": task.command,
        "state": task.state.name,
        "assignedAt": task.assignedAt,
        "updatedAt": task.updatedAt,
        "assignee": task.assignee,
        "exitcode": task.exitcode
    }

def serializeTaskDetail(task):
    t = serializeTask(task)
    t["output"] = task.output
    t["stats"] = task.stats
    t["result"] = task.result
    return t

def serializeTaskResult(task):
    return {
        "id": task.id,
        "command": task.command,
        "state": task.state.name,
        "assignee": task.assignee,
        "exitcode": task.exitcode,
        "output": task.output,
        "stats": task.stats,
        "result": task.result
    }

def serializeEnv(env):
    return {
        "dockerfile": env.dockerfile,
        "params": {e.key: e.value for e in env.params},
        "cpuLimit": env.cpuLimit,
        "memoryLimit": env.memoryLimit,
        "cpuTimeLimit": env.cpuTimeLimit,
        "wallClockTimeLimit": env.wallClockTimeLimit
    }

@app.route("/api/suites")
def get_suites():
    suites = db.session.query(BenchmarkSuite).order_by(BenchmarkSuite.created.desc()).all()
    return {
        "start": 0,
        "end": len(suites),
        "suites": [serializeSuiteOverview(x) for x in suites]
    }

@app.route("/api/suites/<id>")
def get_suite(id):
    suite = db.session.query(BenchmarkSuite).get_or_404(id)
    return serializeSuiteDetail(suite)

@app.route("/api/suites/<id>/results")
def get_suite_results(id):
    suite = db.session.query(BenchmarkSuite).get_or_404(id)
    return serializeSuiteResults(suite)

@app.route("/api/tasks/<id>")
def get_task(id):
    task = db.session.query(BenchmarkTask).get_or_404(id)
    return serializeTaskDetail(task)




