"""Module implementing multithreaded architectures for faster executions
(see example)

"""

__all__ = ['ParallelActions', 'Action']

from threading import Thread
from collections import deque


class ParallelActions(object):
    """Execute multiple action in parallel on a number of threads
    
    Thread safety of actions must be taken care of by the provider of the actions!!
    
    
    """
    workers = {}

    def __init__(self, nthreads = 2):
        self.actions = deque()
        self.nthreads = nthreads
        self.threads = None
        self.working = False

    def addAction(self, action, args = None, kwargs = None):
        """Add a action to the queue of actions to do
        
        action - a callable action
        args - positionnal argument tuple for this action
        kwargs - keyword arguments for the action
        
        """
        if self.working:
            return
        if isinstance(action, Action):
            self.actions.append(action)
        else:
            self.actions.append(Action(action, args, kwargs))

    def execute(self):
        """Start working on the tasks
        Once started, no more tasks can be added
        """
        self.working = True
        self.threads = [self.Worker(self.actions, i, self) for i in range(1, self.nthreads + 1)]
        for th in self.threads:
            th.start()
        # self.actions.put(None)

        for th in self.threads:
            th.join()

    def stop(self):
        """Stop polling new tasks from the queue
        Waits for all worker threads to finish their current task
        
        """
        self.working = False

    class Worker(Thread):
        """A worker (Thread) that does the job"""

        def __init__(self, actions, num, parent):
            """Prepare a worker
            
            actions - the queue of actions to poll from
            num - the number of the worker
            """
            Thread.__init__(self, name = "Worker Thread - %s" % num)
            self.actions = actions
            self.parent = parent

        def run(self):
            while self.parent.working:
                try:
                    self.actions.popleft().execute()
                except IndexError:
                    break


class Action(object):
    """An action to perform"""

    def __init__(self, action, args = None, kwargs = None):
        assert callable(action), "target must be callable"
        if args is None : args = []
        if kwargs is None : kwargs = {}
        self.action = action
        self.args = args
        self.kwargs = kwargs
        self.result = None

    def execute(self):
        self.result = self.action(*self.args, **self.kwargs)

    def __call__(self):
        self.execute()

    def getResult(self):
        return self.result

