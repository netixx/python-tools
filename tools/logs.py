"""Module providing unified logging interface

Provide convenient handlers for logging

Current implementation is based on the logging module (Facade implementation)

"""
__all__ = ['getLogger', 'getDefaultFormatter', 'addStdoutAndStdErr', 'addDailyRotatingHandler', 'addErrorLog', 'addBasicLog']

import logging
import logging.handlers

DEFAULT_LOG_FORMAT = '%(asctime)s : %(levelname)s\t: %(message)s '
DEFAULT_LOG_DATE_FORMAT = '%d/%m/%Y %H:%M:%S'

defaultFormatter = None


def getLogger(name = None):
    """get a logger by its name"""
    return logging.getLogger(name)


def getDefaultFormatter():
    """Returns the default formatter"""
    global defaultFormatter
    if defaultFormatter is None:
        defaultFormatter = logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_LOG_DATE_FORMAT)
    return defaultFormatter


def addStdoutAndStdErr(outLevel = logging.INFO, logger = getLogger(), formatter = getDefaultFormatter()):
    """Adds printing to stdouts and stderrs"""
    import sys

    logger.setLevel(outLevel)
    # sets console logging options
    stdouts = logging.StreamHandler(sys.stdout)
    stdouts.setLevel(outLevel)
    stdouts.setFormatter(formatter)
    logger.addHandler(stdouts)

    # always log errors to stderr
    stderrs = logging.StreamHandler(sys.stderr)
    stderrs.setLevel(logging.ERROR)
    logger.addHandler(stderrs)
    stderrs.setFormatter(formatter)


def addDailyRotatingHandler(filename, logsToKeep = 7, logger = getLogger(), formatter = getDefaultFormatter(), logLevel = logging.INFO):
    """Create a new file each day and delete files older that logToKeep days"""
    fileLog = logging.handlers.TimedRotatingFileHandler(filename = filename,
                                                        when = 'D',
                                                        interval = 1,
                                                        backupCount = logsToKeep,
                                                        encoding = None,
                                                        delay = False,
                                                        utc = True)
    fileLog.setFormatter(formatter)
    fileLog.setLevel(logLevel)
    logger.addHandler(fileLog)


def addBasicLog(filename, logLevel = logging.INFO, logger = getLogger(), formatter = getDefaultFormatter()):
    """Basic log file, append all logging to a file"""
    fileLog = logging.FileHandler(
        filename = filename,
        mode = 'a')
    fileLog.setFormatter(formatter)
    fileLog.setLevel(logLevel)
    logger.addHandler(fileLog)


def addErrorLog(filename, logger = getLogger(), formatter = getDefaultFormatter()):
    """Logs all event above error to a file, overwriting old file"""
    fileLogErr = logging.FileHandler(
        filename = filename,
        mode = 'w')
    fileLogErr.setFormatter(formatter)
    fileLogErr.setLevel(logging.ERROR)
    logger.addHandler(fileLogErr)
