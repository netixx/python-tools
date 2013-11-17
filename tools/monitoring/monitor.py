"""Classes for monitoring

Implementation of monitors (currently implemented : flexLm monitor)

"""

__all__ = ['FlexLmManager']

import os
import re
from system import Console
import logging
from datetime import datetime
import time
from threading import Thread, Event, RLock
from .containers import ServerData


class FlexLmManager(object):
    """ FlexLmManager
    Manages interaction with the lmutil program
        target: type of tool to monitor:
            DOORS
    Also performs server reload and restart
    """
    STAT_COMMAND_TEMPLATE = '"{flexPath}" lmstat -c {port}@{host} -f {featureName}'
    DEFAULT_FLEX_SERVICENAME = "FLEXlm License Manager"
    DEFAULT_FLEX_PORT = 19353
    flexlmExcludeGroup = "GROUP_DOORS_EXCLUDE"
    DEFAULT_FLEX_OPTFILE_EXT = ".opt"

    def __init__(self,
                 config,
                 logSaver):
        """Create a new monitor.
        config - instance of FlexLmManager.Configuration
        logSaver - instance of LogSaver
        """
        assert isinstance(config, self.Configuration)
        self.config = config
        self.logSaver = logSaver
        self.logSaver.setLogger(self.config.logger)
        assert os.path.isfile(self.config.flexPath), "FlexLM tools not found at " + self.config.flexPath
        self.lmRestartCommands = []
        self.hostMonitors = {}
        snapshotLock = RLock();
        for shost in config.hostToMonitor:
            host = shost.upper()
            cmd = self.STAT_COMMAND_TEMPLATE.format(flexPath = self.config.flexPath, host = shost, featureName = self.config.featureName, port = self.config.flexPort)
            self.hostMonitors[host] = self.ServerMonitor(ServerData(host), cmd, self.config.featureName, self.config.logger, snapshotLock, self.config.snapshotLogger)
            self.hostMonitors[host].start()

        self.lmRestartCommands.append('"%s" lmdown -c %s@%s -vendor %s -q' % (self.config.flexPath, self.config.flexPort, self.config.currentHost, self.config.vendor))
        self.lmRestartCommands.append('"%s" lmreread -c %s@%s -vendor %s' % (self.config.flexPath, self.config.flexPort, self.config.currentHost, self.config.vendor))

        self._numberUsages = {}
        self._userData = {}
        self.lastDumpDate = None
        self.config.logger.info("Started FlexLmManager monitor for feature %s", self.config.featureName)

    def terminate(self):
        """Terminates the monitors (ends the worker threads)"""
        for monitor in self.hostMonitors.values():
            monitor.terminate()
        self.config.logger.info("FlexLmManager monitor terminated")

    def getAllServerData(self):
        """Return ServerData Objects that contains the result of the monitoring"""
        ret = []
        for h in self.hostMonitors.values():
            ret.append(h.data)
        return ret

    def getServerData(self, host):
        """Return a ServerData object for the given host, None if host is unknown"""
        h = host.upper()
        if self.hostMonitors.has_key(h):
            return self.hostMonitors[h].data
        return None

    def isAlive(self, shost):
        """Checks whether the server shost is alive
        shost - address (string) of the server to test
        
        Test is done by searching for the feature lines and seeing if total licens issued is greater than 0
        """
        cmd = self.STAT_COMMAND_TEMPLATE.format(flexPath = self.config.flexPath, host = shost, featureName = self.config.featureName, port = self.config.flexPort)
        result = Console.sendCommand(cmd)
        ok = re.compile(r"Users of .*?Total of (\d+) licenses issued.*?Total of (\d+) licenses in use.*")
        for line in result.getResult().splitlines():
            res = ok.match(line)
            if res is not None:
                # there is a least one license issued
                if int(res.group(1)) > 0:
                    return True
                else:
                    self.config.logger.warning("Status line found but number of issued is not strictly positive : %s", line);
        return False

    def monitorLicense(self):
        """Extract license data from lmstat dump using one thread per server"""
        activeUsersNum = 0
        for oMonitor in self.hostMonitors.values():
            oMonitor.monitor()
            self.lastDumpDate = oMonitor.data.lastDump
            activeUsersNum += oMonitor.lastScannedUsers
        # end loop servers
        self.config.logger.info("Application : %s has %3d active users" , self.config.featureName, activeUsersNum)

    def reloadServer(self):
        """Reload the license server through lmdow and lmreread, use with caution
        
        Failsafe : test if server is alive after 1 minute
        """
        self.config.logger.info("Reloading server")
        for command in self.lmRestartCommands:
            self.config.logger.debug("Sending command %s", command)
            if not self.config.mock :
                result = Console.sendCommand(command)
                if result.hasErrors():
                    self.config.logger.warning("Reloading command terminated with errors : %s", result.getErrors())
                    self.restartServer()
                    break
                else:
                    self.config.logger.info("Reload command successful : %s", command)
                time.sleep(60)
        if not self.isAlive(self.config.currentHost):
            self.config.logger.warning("Server is not alive, restarting")
            self.restartServer()

    def restartServer(self):
        """Restart (service restart) the server, saving the logs and remerging them at the same time"""
        self.logSaver.backupLog()
        self.config.logger.info("Restarting server service...")
        stopResult = Console.sendCommand('net stop "%s"' % self.config.flexServiceName)
        if stopResult.hasErrors():
            self.config.logger.warning("Stop command terminated with errors : %s", stopResult.getErrors())
        else :
            self.config.logger.info("Service stop successful")
        startResult = Console.sendCommand('net start "%s"' % self.config.flexServiceName)
        if startResult.hasErrors():
            self.config.logger.warning("Restart command terminated with errors : %s", startResult.getErrors())
        else :
            self.config.logger.info("Service start successful")
        self.logSaver.mergeLastLogs()

    def ensureServerAvailability(self):
        """Make sure that server is available by checking if server isAlive and restarting if needed"""
        self.config.logger.info("Checking if server is available...")
        if not self.isAlive(self.config.currentHost):
            self.config.logger.info("Server %s is down... attempt to restart...", self.config.currentHost)
            self.restartServer()
            return False
        else:
            self.config.logger.info("Server %s is ok.", self.config.currentHost)
            return True

    def writeFlexOptFile(self, content = None):
        """Writes the flexOpt file with content
        content - content to write to the opt file
        
        If content is None, write the default flex opt file
        
        """
        opfFileBuffer = "GROUP DOORSUSER SBX\nEXCLUDE DOORS GROUP DOORSUSER\n"
        if content is not None:
            opfFileBuffer += content
        # write option file
        with open(self.config.flexOptFile, 'w') as optFile:
            optFile.writelines(opfFileBuffer)

        self.config.logger.info("Option file rewritten")

    @staticmethod
    def generateDenyGroup(userList, groupName = None):
        """Generate the deny string for the flex server
        userlist - list of usernames (strings)
        groupName - name of the exclusion group (default is DEFAULT_EXCLUDE_GROUP
        
        """
        if groupName is None:
            groupName = FlexLmManager.flexlmExcludeGroup
        if len(userList) > 0:
            ret = "GROUPCASEINSENSITIVE ON\n"
            ret += "GROUP %s %s\n" % (groupName, " ".join(userList));
            ret += "EXCLUDE DOORS GROUP %s\n" % groupName
            return ret
        return ""

    class ServerMonitor(Thread):
        """Main worker, does the actual job of parsing the output and places it in a ServerData object"""

        def __init__(self, oServer, statusCommand, featureName, logger, snapshotLock, snapshotLogger):
            """Create a new Worker
            oServer - ServerData instance, where the information will be saved
            statusCommand - Command to send to get the status dump
            featureName - name of feature to monitor
            logger - logger instance
            """
            Thread.__init__(self, name = "ServerMonitor-%s" % oServer.hostname)
            self._serverData = oServer
            self._featureName = featureName
            self._monitorEvent = Event()
            self._monitorEvent.clear()
            self.__resultCollected = Event()
            self.isRunning = True
            self.logger = logger
            self._statusCommand = statusCommand
            self._snapshotLock = snapshotLock
            self._snapshotLogger = snapshotLogger

        def monitor(self):
            """Monitor the server once (gets the data)"""
            self.__resultCollected.clear()
#             self._serverData.resetUsage()
            if not self._monitorEvent.is_set():
                self._monitorEvent.set()

        def terminate(self):
            self.isRunning = False
            self._monitorEvent.set()
            self.join()

        def run(self):
            """Gets and parses the results 
            Dump starts with a date line:
                Flexible License Manager status on Tue 9/3/2013 09:52
            then the feature line with the total:
                Users of DOORS:  (Total of 56 licenses issued;  Total of 39 licenses in use)
            then the user data:
                parse examples:
                    SBA151 VSDS-BIE-L0240 VSDS-BIE-L0240 (v1.000) (BIE-PVCS-01/19353 212), start Wed 4/12 12:32
                    SYSTEM bie-pvcs-01 bie-pvcs-01 (v3.000) (BIE-PVCS-01/19353 421), start Wed 4/12 14:53
                    SBX035 VSDS-BIE-L0150 VSDS-BIE-L0150 (v6.000000) (VSDS-BIE-S002/7587 677), start Wed 4/12 14:58
                    SBX114 vsds-bie-w0063 bie-pvcs-01 (v8.000) (bie-pvcs-01/27000 1036), start Wed 4/12 12:49
                    SBX216 vebi7462 bie-pvcs-01 (v8.000) (bie-pvcs-01/27000 826), start Wed 4/12 10:28
                    rebecca.woodard.ext doorsts VIC-HUD-L017 telelogic (v2009.0602) (bie-pvcs-01/19353 3344), start Mon 3/21 16:37
                    Surfer rst5 rst5 telelogic (v2009.0602) (bie-pvcs-01/19353 129), start Tue 3/22 9:58
                    anne-clarissa doorsts VIC-TUA-L0416 telelogic (v2009.0602) (bie-pvcs-01/19353 1334), start Mon 3/21 17:39
            """
            # Flexible License Manager status on Tue 12/4/2012 07:49
            licDatePattern = re.compile(r"\s*{startLine}.+?(\d+/\d+/\d+\s\d+:\d+)\s*".format(startLine = r"Flexible License Manager status on"))
            totalPattern = re.compile(r"Users of {featureName}.*?Total of (\d+) licenses issued.*?Total of (\d+) licenses in use.*".format(featureName = self._featureName))
            userDataPattern = re.compile(r"\s+([\w.-]+)\s+([\w-]+)\s+([\w-]+?)\s+([\w -]*)\(.+\)\s\(.+\), start \w+ (\d+/\d+\s\d+:\d+)\s*")
            featureLinePattern = re.compile(r"Users of\s.*")
            while self.isRunning:
                self._monitorEvent.wait()
                if not self.isRunning:
                    break
                dumpLines = Console.sendCommand(self._statusCommand).getSplitResult()
                if len(dumpLines) <= 0:
                    self.logger.warning("No dump received for %s", self._statusCommand)
                    self._monitorEvent.clear()
                    continue
                dumpDate = None
                feature = False
                relevantLines = []
                lineCounter = -1
                for singleLine in dumpLines:
                    lineCounter += 1
                    if not len(singleLine) > 0:
                        continue
                    self.logger.debug(singleLine)
                    # find date of dump generation
                    if dumpDate is None:
                        dateMatch = licDatePattern.match(singleLine)
                        if dateMatch is not None:
                            self.logger.debug("License date matched for line : %s", singleLine)
                            # construct the date
                            dumpDate = datetime.strptime(dateMatch.group(1), "%m/%d/%Y %H:%M")
                            relevantLines.append(lineCounter)
                            continue
                    # end date checking
                    # Users of DOORS:  (Total of 56 licenses issued;  Total of 14 licenses in use)
                    if dumpDate is not None:
                        # find the beginning of the feature
                        if not feature:
                            fMatch = totalPattern.match(singleLine)
                            if fMatch is not None:
                                feature = True
                                self._serverData.usedLicenses = fMatch.group(2)
                                self._serverData.totalLicenses = fMatch.group(1)
                                relevantLines.append(lineCounter)
                        else:
                            userMatch = userDataPattern.match(singleLine)
                            if userMatch is not None:
                                # add the year found in the dump date because startUsageTimeStr has no year
                                loginDate = datetime.strptime(str(dumpDate.year) + "/" + userMatch.group(5), "%Y/%m/%d %H:%M")
                                self._serverData.addUsage(dumpDate, userMatch.group(1), loginDate , userMatch.group(3), userMatch.group(2))
                                relevantLines.append(lineCounter)
                            featureLine = featureLinePattern.match(singleLine)
                            if featureLine is not None:
                                feature = False
                                break
                # end loop dumplines
                self.logger.info("Total licenses read for host %s : %s/%s", self._serverData.hostname, self._serverData.usedLicenses, self._serverData.totalLicenses)
                self._serverData.lastDump = dumpDate
                self._monitorEvent.clear()
                self.__resultCollected.set()
                with self._snapshotLock:
                    self._snapshotLogger.info("New dump from %s", self._serverData.hostname)
                    for lineNum in relevantLines:
                        self._snapshotLogger.info(dumpLines[lineNum])
                    self._snapshotLogger.info("End of dump")
            # end while

        @property
        def data(self):
            """Gets the collected Data (waits for the collection to be over)"""
            self.__resultCollected.wait()
            return self._serverData

        @property
        def lastScannedUsers(self):
            """Get number of users found in the last dump"""
            return len(self._serverData.userUsage)

    class Configuration(object):
        """Configuration Data for the FlexLmMonitor"""
        def __init__(self,
             currentHost,
             hostToMonitor,
             featureName,
             flexPath,
             flexVendor,
             flexOptFileName = None,
             flexPort = None,
             flexServiceName = None,
             logger = logging.getLogger(),
             snapshotLogger = logging.getLogger(),
             mock = False):
            """Creates a new Configuration
            currentHost - host (string) on which the script is running (for restarts)
            hostToMonitors - array of address strings to monitor
            featureName - name of the feature to monitor (eg. DOORS)
            flexPath - local os path to the flexLm lmstat executable
            flexVendor - the vendor of the licenses (eg. telelogic)
            flexOptFileName - the name of the option file (default is flexVendor.opt)
            flexPort - port of the FlexLm server
            flexServiceName - local service name
            logger - logger for general purposes
            snapshotLogger - logger for the snapshots (copy the output)
            mock - should sensible operations be done (restarts...)
            
            """
            if flexOptFileName is None:
                flexOptFileName = flexVendor + FlexLmManager.DEFAULT_FLEX_OPTFILE_EXT
            if flexPort is None:
                flexPort = FlexLmManager.DEFAULT_FLEX_PORT
            if flexServiceName is None :
                flexServiceName = FlexLmManager.DEFAULT_FLEX_SERVICENAME

            self._currentHost = currentHost
            self._hostToMonitor = hostToMonitor
            self._featureName = featureName
            self._flexPath = flexPath
            self._vendor = flexVendor
            self._flexPort = flexPort
            self._flexOptFile = flexOptFileName
            self._flexServiceName = flexServiceName
            self._logger = logger
            self._snapshotLogger = snapshotLogger
            self._mock = mock

        @property
        def vendor(self):
            return self._vendor

        @property
        def currentHost(self):
            return self._currentHost
        
        @property
        def hostToMonitor(self):
            return self._hostToMonitor
        
        @property
        def featureName(self):
            return self._featureName
        
        @property
        def flexPath(self):
            return self._flexPath
        
        @property
        def flexPort(self):
            return self._flexPort

        @property
        def flexOptFile(self):
            return self._flexOptFile

        @property
        def flexServiceName(self):
            return self._flexServiceName
        
        @property
        def logger(self):
            return self._logger
        
        @property
        def snapshotLogger(self):
            return self._snapshotLogger

        @property
        def mock(self):
            return self._mock


class LogSaver(object):
    """Backup and merge the given logs
    backup is done in logSaveDir, date of backup is in the name of the file
    merge is done in place with the last log saved
    
    Root logger is used unless a logger is supplied with setLogger or as parameter
    
    NOTE:Works only in windows
    
    """
    
    def __init__(self, logSaveDir, logFilePath, logger = logging.getLogger()):
        """Create a new logSaver
        logSaveDir - directory to save the backups
        logFilePath - path of the log to save
        
        """
        self.logSaveDir = logSaveDir
        self.logFilePath = logFilePath
        self.lastLogSave = None
        self.logger = logger

    def setLogger(self, logger):
        """Sets the logger"""
        self.logger = logger

    def backupLog(self):
        """Backup the logs to the logSaveDir via copy
        backup contains the date in the filename
        
        Populates the self.lastLogSave variable
        """
        self.logger.info("Saving logs")
        if not os.path.exists(self.logSaveDir):
            os.mkdir(self.logSaveDir)
        if not os.path.exists(self.logFilePath):
            self.logger.warning("No log file found, nothing to backup")
            return
        now = datetime.now().strftime("%Y-%m-%d_%H_%M")
        filename = "log-%s.log" % now
        self.lastLogSave = os.path.join(self.logSaveDir, filename)
        result = Console.sendCommand('copy /Y /B "%s" "%s" ' % (self.logFilePath, self.lastLogSave))
        if result.hasErrors():
            self.logger.warning("Error during log backup %s", result.getErrors())
        else:
            self.logger.info("Log save as %s" % self.lastLogSave)

    def mergeLastLogs(self):
        """Merges the lastSaveLog with the current logFile (prepends the last log), maintaining
        chronology of the logs
        
        """
        # nothing to merge !
        if self.lastLogSave is None:
            self.logger.warning("No previous saved log to merge")
            return
        self.logger.info("Merging logs")
        # temp filename
        tempLog = self.logFilePath + "s"
        # send the copy command
        result = Console.sendCommand('copy /Y /B "%s" "%s" && copy /Y /B "%s"+"%s" "%s" && del "%s"' % (self.logFilePath,
                                                                                                        tempLog,
                                                                                                        self.lastLogSave,
                                                                                                        tempLog,
                                                                                                        self.logFilePath,
                                                                                                        tempLog))
        if result.hasErrors():
            self.logger.warning("Error while merging logs : %s", result.getErrors())
        else :
            self.logger.info("Logs merged successfully")
