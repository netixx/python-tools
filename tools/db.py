"""Module regrouping diverse db interface

Currently implemented : oracle

"""

__all__ = ['Oracle']

import logging
from collections import deque
import time

import cx_Oracle


class Oracle(object):
    """Object that does query on a oracle database
        Load the query (as a method) with addAction and execute with executeAll or executeOne
        
    """

    MAX_CONNECT_TRIES = 3
    WAIT_TIME = 60

    def __init__(self, config):
        """Creates a new Oracle interface
        
        config - configuration data, instance of Oracle.Configuration
        
        """
        self.connection = None
        self.actions = deque()
        assert isinstance(config, Oracle.Configuration)
        self.config = config
        self.logger = config.getLogger()
        self.connectionAttempts = 0

    def addAction(self, method):
        """Add an action (as callable object) to be performed on the database
        the following parameters are supplied : connection (to the db) and logger (for logging)
        
        """
        self.logger.debug("Adding action to buffer")
        self.actions.append(method)

    def executeAll(self):
        """Executes all actions in the buffer (self.actions) in FIFO order"""
        try:
            self.__connect()
            # execute db actions
            for method in self.actions:
                self.__execute(method)
        except Exception as e:
            self.logger.error("Could not contact the database : %s", e)
        finally:
            self.__close()

    def executeOne(self):
        """Executes the first action of the queue (FIFO)"""
        try:
            self.__connect()
            # insert monthly update of license usage
            self.__execute(self.actions.popleft())

        except Exception as e:
            self.logger.error("Could not contact the database : %s", e)
        finally:
            self.__close()

    def __execute(self, action):
        if not self.config.isMock():
            self.logger.debug("Executing query")
            action(self.connection, self.logger)

    def __connect(self):
        self.logger.debug("Contacting the database...")
        # try to connect a couple of times
        while self.connectionAttempts < self.MAX_CONNECT_TRIES:
            try:
                self.connection = cx_Oracle.connect(*self.config.getConnectionParam())
                self.connectionAttempts = 0
                break
            except cx_Oracle.Error as e:
                error, = e.args
                self.logger.error("Could not contact the database : %s, %s, %s", error.code, error.message, error.context)
                if self.connectionAttempts == self.MAX_CONNECT_TRIES:
                    raise e
                else:
                    self.connectionAttempts += 1
                    time.sleep(self.WAIT_TIME)
                    self.logger.info("Trying to connect once more %s/%s", self.connectionAttempts, self.MAX_CONNECT_TRIES)

        self.logger.debug("Connected to database")

    def __close(self):
        try:
            if self.connection is not None and self.connectionAttempts == 0:
                self.connection.close()
                self.logger.debug("Connection closed")
        except Exception as e:
            self.logger.warning("Error while closing the connection to the database : %s", e)


    class Configuration(object):
        """Configuration information for the mailer"""

        DEFAULT_DB_PORT = 1521

        def __init__(self,
                     userName = None,
                     password = None,
                     hostName = None,
                     port = None,
                     sid = None,
                     mock = False,
                     logger = None):
            """Creates a new Configuration
            
            userName - user name to connect to the db
            password - password for the db
            hostName - host of the db
            port - port of the db
            sid - service ID of the oracle db
            mock - sould the actions actually be performed ?
            logger - a Logger class for logging purposes
            
            """
            if (userName is None
                or password is None
                or hostName is None
                or sid is None):
                raise Exception("A connection parameter is missing")

            if port is None:
                port = self.DEFAULT_DB_PORT
            self.__port = port
            self.__userName = userName
            self.__sid = sid
            self.__password = password
            self.__hostName = hostName
            self.__mock = mock
            if logger is None:
                self.__logger = logging.getLogger()
            else:
                self.__logger = logger

        def getDsn(self):
            return cx_Oracle.makedsn(self.__hostName, self.__port, self.__sid)

        def getConnectionParam(self):
            return self.__userName, self.__password, self.getDsn()

        def isMock(self):
            return self.__mock

        def getLogger(self):
            return self.__logger


