'''
Generic container for monitoring purposes

Warning : the protected fields (__field) makes it impossible for the children to have access 
to the parent's fields

'''

__all__ = ['ServerData', 'TimeMonitoredUser']
import datetime

class BaseUser(object):
    def __init__(self, uid = 'NONE'):
        self.__uid = uid.upper()
        
    def getUid(self):
        return self.__uid
    
    def setUid(self, uid):
        if self.__uid == 'NONE' or self.__uid is None:
            self.__uid = uid.upper()
            
class User(BaseUser):
    def __init__(self, uid = 'NONE', name = None , mail = None):
        BaseUser.__init__(self, uid)
        self._name = name
        self._mail = mail

    def getSafeName(self):
        if self._name is None:
            return self.getUid()
        return self.getName()

    def getMail(self):
        return self._mail

    def getName(self):
        return self._name

    def __str__(self):
        return "%s;%s;%s" % (self.getUid(), self._name, self._mail)

class _FlexUser(object):
    def __init__(self, machine, server):
        self.__machine = machine
        self.__server = server

    def getMachine(self):
        return self.__machine

    def getServer(self):
        return self.__server

    def udpateServer(self, server):
        self.__server = server

    def updateMachine(self, machine):
        self.__machine = machine

class _TimedUser(object):
    def __init__(self):
        self.__usageTime = datetime.timedelta(0)
        self.__lastUpdate = None

    def getLastUpdate(self):
        return self.__lastUpdate

    def incrementUsageTime(self, increment):
        self.__usageTime += increment

    def setLastUpdate(self, lastUpdate):
        self.__lastUpdate = lastUpdate

    def getUsageTime(self):
        return self.__usageTime

    def resetUsageTime(self):
        self.__usageTime = datetime.timedelta(0)


class _TimeMonitoredUser(_TimedUser):
    """Contains data of user """

    DEFAULT_MAXIMUM_USAGE_TIME = 10 * 3600

    def __init__(self):
        _TimedUser.__init__(self)
        self.__warned = False
        self.__banned = False
        self.__bannedTime = datetime.timedelta(0)
        self.__allowedUsageTime = self.DEFAULT_MAXIMUM_USAGE_TIME

    def getMaxAllowedUsage(self):
        return self.__allowedUsageTime

    def getTotalUsageTime(self):
        return self.__bannedTime + self.getUsageTime()

    def grantUsageTime(self, additionnalTime = 3600):
        self.__allowedUsageTime += additionnalTime

    def addBannedTime(self, bannedTime):
        self.__bannedTime += bannedTime

    def isBanned(self):
        return self.__banned

    def isWarned(self):
        return self.__warned

    def setBanStatus(self, isBanned):
        self.__banned = isBanned

    def setWarnStatus(self, isWarned):
        self.__warned = isWarned

    def setUnban(self):
        self.__banned = False
        self.__warned = False

class FlexTimedUser(BaseUser, _TimedUser, _FlexUser):
    def __init__(self, uid, machine, server):
        BaseUser.__init__(self, uid)
        _FlexUser.__init__(self, machine, server)
        _TimedUser.__init__(self)
        self.__increment = datetime.timedelta(0)

    def getIncrement(self):
        return self.__increment

    def setIncrement(self, increment):
        self.__increment = increment

class TimeMonitoredUser(User, _TimeMonitoredUser):
    def __init__(self, uid = 'NONE', name = None, mail = None):
        User.__init__(self, uid, name, mail)
        _TimeMonitoredUser.__init__(self)


class ServerData(object):
    """Data for representing a Server
    addUsageData by the addUsage field
    get all results by the userUsage field
    usedLicenses and freeLicenses return the corresponding values for the server
    """

    def __init__(self, hostName):
        """Creates a new container
        hostname - hostname of the server (or ip address)
        """
        self._hostName = hostName
        self._usedLicenses = 0
        self._totalLicenses = 0
        self._userUsage = None
        self.resetUsage()
        self._lastDumpDate = None

    @property
    def hostname(self):
        return self._hostName

    @property
    def usedLicenses(self):
        return self._usedLicenses

    @usedLicenses.setter
    def usedLicenses(self, freeNum):
        self._usedLicenses = int(freeNum)

    @property
    def totalLicenses(self):
        return self._totalLicenses

    @totalLicenses.setter
    def totalLicenses(self, totalNum):
        self._totalLicenses = int(totalNum)

    @property
    def userUsage(self):
        return self._userUsage

    def addUsage(self, dumpDate, user, loginDate, userHostName, server = None):
        """Update user data in the database with the given information"""
        # do only use UC
        user = user.upper()
        oUser = self.getUserByUid(user)
        # user not known in current db
        if oUser is None :
            oUser = FlexTimedUser(uid = user, machine = userHostName, server = server)
            oUser.resetUsageTime()
            increment = dumpDate - loginDate
            self.storeUser(oUser)
        else:
            # user already known
            # we haven't seen the user on the last dump (he was not connected)
            if self._lastDumpDate != None and oUser.getLastUpdate() < self._lastDumpDate:
                oUser.setLastUpdate(loginDate)

            increment = dumpDate - oUser.getLastUpdate()

            # if the user is logged twice or more on the same server, we apply a default value for
            # for the increment (adding to the old increment)
            if oUser.getLastUpdate() == dumpDate:
                if self._lastDumpDate is None :
                    delta = dumpDate - loginDate
                else :
                    delta = dumpDate - self._lastDumpDate
                increment = oUser.getIncrement() + delta

            oUser.updateMachine(userHostName)
            oUser.udpateServer(server)

        oUser.incrementUsageTime(increment)
        oUser.setIncrement(increment)
        oUser.setLastUpdate(dumpDate)

    def storeUser(self, user):
        self._userUsage[user.getUid()] = user

    def getUserByUid(self, uid):
        if self._userUsage.has_key(uid.upper()):
            return self._userUsage[uid.upper()]
        return None

    def resetUsage(self):
        self._userUsage = {}

    def resetUserUsage(self, user):
        del self._userUsage[user.upper()]

    @property
    def lastDump(self):
        return self._lastDumpDate

    @lastDump.setter
    def lastDump(self, dumpDate):
        self._lastDumpDate = dumpDate

    def __str__(self):
        usage = ""
        for user in self.userUsage:
            usage += "%s\n" % (user,)
        return "Server data for host %s at : %s, %s/%s licenses\nUser statistics : \n%s" % (self.hostname, self.lastDump, self.usedLicenses, self.totalLicenses, usage)
