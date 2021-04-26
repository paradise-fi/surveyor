from concurrent.futures import Future
from contextlib import ExitStack

def withCleanup(fun, onExit):
    """
    Wrap fun such that onExit is called upon return (event when Exception is
    thrown).
    """
    def wrapper(*args, **kwargs):
        with ExitStack() as exitStack:
            exitStack.push(onExit)
            return fun(*args, **kwargs)
    return wrapper


def asFuture(value):
    """
    Wrap value in a future
    """
    f = Future()
    f.set_result(value)
    return f