from surveyor import app, db
from surveyor.models import *
from flask import request

def serializeSuiteOverview(suite):
    return {
        "id": suite.id,
        "created": suite.created,
        "author": suite.author,
        "taskCount": len(suite.tasks),
        "completedTaskCount": suite.completedTaskCount(),
        "assignedTaskCount": suite.assignedTaskCount(),
        "description": suite.description
    }

def serializeSuiteDetail(suite):
    s = serializeSuiteOverview(suite)
    s["env"] = serializeEnv(suite.env)
    s["tasks"] = [serializeTask(x) for x in suite.tasks]
    return s

def serializeSuiteResults(suite):
    return {
        "id": suite.id,
        "description": suite.description,
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

@app.route("/api/suites", methods=["GET", "POST"])
def suites_endpoint():
    if request.method == "POST":
        return new_suite()
    return get_suites()

def get_suites():
    suites = db.session.query(BenchmarkSuite).order_by(BenchmarkSuite.created.desc()).all()
    return {
        "start": 0,
        "end": len(suites),
        "suites": [serializeSuiteOverview(x) for x in suites]
    }

def new_suite():
    data = request.get_json()
    username = request.environ.get("AUTH_USER", "web")
    if data is None:
        return "Invalid data", 400
    try:
        suite = BenchmarkSuite(author=username, description=data["description"],)
        suite.env = RuntimeEnv(
            dockerfile=data["dockerfile"],
            cpuTimeLimit=data["cputimelimit"],
            wallClockTimeLimit=data["walltimelimit"],
            cpuLimit=data["cpulimit"],
            memoryLimit=data["memorylimit"])
        # TBA Params
        for t in data["tasks"]:
            if not isinstance(t, str):
                raise RuntimeError(f"Task is supposed to be string, got {type(t)} instead: '{t}'")
            suite.tasks.append(BenchmarkTask(command=t, state=TaskState.pending))
        db.session.add(suite)
        db.session.commit()
        return {
            "id": suite.id
        }
    except Exception as e:
        db.session.abort()
        return str(e), 400

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




