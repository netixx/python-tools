"""
Module implementing class definitions for monitoring strategies.

"""
import heapq
import itertools
import logging

__all__ = ['ApplicationState',
           'UserEvent',
           'StrategyEnforcer',
           'ManagementStrategy',
           'InvalidStrategyException',
           'InvalidServiceException']


class StrategyEnforcer(object):
    HIGHEST_PRIORITY = 0
    HIGH_PRIORITY = 2
    NORMAL_PRIORITY = 4
    LOW_PRIORITY = 8
    LOWEST_PRIORITY = 16

    def __init__(self, logger = logging.getLogger()):
        self._strategies = []
        self._services = {}
        self._logger = logger

    def addStrategy(self, strategy, priority = None):
        if priority is None:
            priority = self.NORMAL_PRIORITY
        if not isinstance(strategy, ManagementStrategy):
            raise InvalidStrategyException("Given object is not a ManagmentStrategy")
        self.__checkServiceRequirements(strategy)
        strategy.setPriority(priority)
        heapq.heappush(self._strategies, strategy)

    def __checkServiceRequirements(self, strategy):
        for service in strategy.requiredServices:
            if not self._services.has_key(service):
                raise InvalidServiceException("Strategy requires services not currently registered with this enforcer : %s" % service)
        return True

    def applyStrategies(self):
        for strategy in self._strategies:
            strategy.applyStrategy(self)

    def cleanupStrategies(self):
        for strategy in self._strategies:
            strategy.cleanup(self)

    def registerService(self, service):
        if not isinstance(service, StrategyService):
            raise InvalidServiceException("Given object is not a StrategyService")
        self._services[service.name] = service

    def getService(self, name):
        return self._services[name]

    @property
    def logger(self):
        return self._logger


class StrategyService(object):
    def __init__(self, name, callback):
        self.__callback = callback
        self.__name = name

    def __call__(self, *args, **kwargs):
        return self.execute(*args, **kwargs)

    def execute(self, *args, **kwargs):
        return self.__callback(*args, **kwargs)

    @property
    def name(self):
        return self.__name


class ManagementStrategy(object):
    count = itertools.count()
    requiredServices = []

    def __init__(self):
        self.__priority = None
        self.__problems = None
        self.__resetProblems()

    def setPriority(self, priority):
        if self.__priority is None:
            self.__priority = (priority, next(self.count))

    @property
    def priority(self):
        return self.__priority

    def __eq__(self, other):
        if not isinstance(other, ManagementStrategy):
            return False
        return self.priority == other.priority

    def __lt__(self, other):
        return self.priority <= other.priority

    def applyStrategy(self, enforcer):
        self.__resetProblems()
        self.strategy(enforcer)

    def strategy(self, enforcer):
        raise NotImplemented("Strategy classes must implement the strategy method")

    def cleanup(self, enforcer):
        pass

    def problems(self):
        return self.__problems

    def __resetProblems(self):
        self.__problems = []


class InvalidStrategyException(Exception):
    pass


class InvalidServiceException(Exception):
    pass
