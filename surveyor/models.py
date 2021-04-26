from surveyor import db
from datetime import datetime
import enum

class BenchmarkSuite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.Column(db.String(50))
    env = db.relationship("RuntimeEnv", back_populates="suite", uselist=False)
    tasks = db.relationship("BenchmarkTask", back_populates="suite", lazy=False)

class RuntimeEnv(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    suite_id = db.Column(db.Integer, db.ForeignKey("benchmark_suite.id"),
        nullable=False)
    suite = db.relationship("BenchmarkSuite", back_populates="env", uselist=False)
    description = db.Column(db.Text)
    dockerfile = db.Column(db.Text)
    params = db.relationship("RuntimeParam", back_populates="env", lazy="joined")
    cpuLimit = db.Column(db.Integer)
    memoryLimit = db.Column(db.Integer)
    timeLimit = db.Column(db.Integer)

class RuntimeParam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    env_id = db.Column(db.Integer, db.ForeignKey("runtime_env.id"),
        nullable=False)
    env = db.relationship("RuntimeEnv", back_populates="params", uselist=False)
    key = db.Column(db.String(100))
    value = db.Column(db.Text)

class TaskState(enum.Enum):
    created = 1
    pending = 2
    assigned = 3
    evaluated = 4
    cancelled = 5

class BenchmarkTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    suite_id = db.Column(db.Integer, db.ForeignKey("benchmark_suite.id"),
        nullable=False)
    suite = db.relationship("BenchmarkSuite", back_populates="tasks", uselist=False)

    command = db.Column(db.Text)
    state = db.Column(db.Enum(TaskState), default=TaskState.created)
    assignedAt = db.Column(db.DateTime, default=None)
    updatedAt = db.Column(db.DateTime, default=None)
    assignee = db.Column(db.String(100), default=None)

    # Exit code of the benchmarking command
    exitcode = db.Column(db.Integer, default=None)
    # Combination of stdout & stderr
    output = db.deferred(db.Column(db.Text, default=None))
    # Time of the actual execution time in microsends
    time = db.Column(db.BIGINT, default=None)
    # Statistics collected by the runner, to be implemented in the future
    stats = db.Column(db.JSON, default=None)
    # The JSON object produced by the evaluation task
    result = db.Column(db.JSON, default=None)

    @staticmethod
    def fetchNew(availableCores, availableMemory):
        """
        Fetch and reserve an unfinished task that fits inside the given limits.
        """
        # TBA extend the query by tasks that are assigned, but haven't been
        # updated in a long time
        tasks = (BenchmarkTask.query
                    .filter_by(state=TaskState.pending)
                    .order_by(BenchmarkTask.id)
                    .limit(1).all())
        if len(tasks) == 0:
            return None
        return tasks[0]

    def acquire(self, assignee):
        """
        Acquire the task to the assignee
        """
        self.state = TaskState.assigned
        self.assignee = assignee
        t = datetime.utcnow()
        self.assignedAt = t
        self.updatedAt = t

    def abandon(self):
        """
        Abandon the task without successfully evaluating it.
        """
        self.state = TaskState.pending
        self.assignedAt = None
        self.updatedAt = None
        self.assignee = None

    def poke(self, output):
        """
        Poke the task - notify the database that the task is still being
        evaluated, update its output.
        """
        self.updatedAt = datetime.utcnow()
        self.output = output

    def finish(self, exitcode, output, time, stats, result):
        """
        Sucessfully finish evaluation of the task
        """
        self.state = TaskState.evaluated
        self.exitcode = exitcode
        self.output = output
        self.time = time
        self.stats = stats
        self.result = result


