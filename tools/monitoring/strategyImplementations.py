"""Implementation of monitoring strategies
Those are strategies to regulate license usage

"""

__all__ = ['KeepFreePercentageBanLongUsersStrategy',
           'WarnUsersBeforeMaxUsageTimeStrategy',
           'ApplicationState',
           'UserEvent']

from strategy import ManagementStrategy
from datetime import datetime
from monitor import FlexLmManager
import copy

class ApplicationState(object):
    """States of the Application"""
    INIT = 0
    FREE = 1
    DENY = 2

class UserEvent(object):
    """An event destined to a DoorsUser"""
    WARN = 'warn'
    BAN = 'ban'
    UNBAN = 'unban'

class KeepFreePercentageBanLongUsersStrategy(ManagementStrategy):
    """Strategies that tries to keep a given percentage of free licenses available on server
    
    When the percentage of free licenses passes bellow the fixed Minimum limit,
    it bans user given by the getUserToBan service. Users are banned from the flexServer for
    keepStateTimeout seconds
    It tries to ensure that no more than Maximum Limit is available after action
    
    setWhen should be called before applying the strategy otherwise datetime.now() is used.
    
    """
    def __init__(self, keepStateTimeout, minFreePercentage, maxFreePercentage = 1):
        """Creates a new instance of the strategy
        keepStateTimeout - duration (in seconds) between state change
        minFreePercentage - minimal percentage to keep free on the server
        maxFreePercentage - max allowed percentage after action
        
        """
        ManagementStrategy.__init__(self)
        self.switchTime = None
        self.keepStateTimeout = keepStateTimeout
        self.minFreePercentage = minFreePercentage
        self.maxFreePercentage = maxFreePercentage
        self.when = None
        self._setWhen = False
        self.currentState = ApplicationState.INIT
        self.bannedUsers = []
        self.idealState = ApplicationState.FREE
        self.requiredServices = ['resetUserUsage',
                                 'getUserToBan',
                                 'writeFlexOptFile',
                                 'notifyEvent',
                                 'scheduleServerReloadOnce',
                                 'getFreePercentage',
                                 'getTotalNumberOfUsers']

    def setWhen(self, when = datetime.now()):
        """Sets the current date"""
        self.when = when
        self._setWhen = True

    def strategy(self, enforcer):
        if not self._setWhen:
            self.setWhen()
        self._setWhen = False
        if self.currentState == ApplicationState.INIT:
            self.currentState = ApplicationState.FREE
            enforcer.logger.info("Ban strategy initialization done!")

        freePercentage = enforcer.getService('getFreePercentage').execute()
        if freePercentage < self.minFreePercentage:
            self.idealState = ApplicationState.DENY
            enforcer.logger.info("Current ideal state: DENY")
        else:
            self.idealState = ApplicationState.FREE
            enforcer.logger.info("Current ideal state: FREE")

        enforcer.logger.debug("FlexLmManager performed: Current state = %s, next state = %s", self.currentState, self.idealState)

        if self.switchTime == None or (self.when - self.switchTime).total_seconds() > self.keepStateTimeout:
            # in case we have been in DENY mode for more than switch Time, allow the previously bannedUsers
            if self.currentState == ApplicationState.DENY and len(self.bannedUsers) > 0:
                self.unBanUsers(enforcer)
                rel = enforcer.getService('scheduleServerReloadOnce').execute()
                if rel is False:
                    enforcer.logger.info("Server reload already scheduled")
                # reset the state so that if next ideal state is DENY, new user can be banned
                self.currentState = ApplicationState.FREE
            if self.currentState != self.idealState:
                if self.idealState == ApplicationState.DENY:
                    enforcer.logger.info("Switched to ApplicationState.DENY")
                    self.bannedUsers = enforcer.getService('getUserToBan').execute()
                    if len(self.bannedUsers) > 0:
                        totalUser = enforcer.getService('getTotalNumberOfUsers').execute()
                        # this should always be positive unless the maxFreePercentage is lower than the warn threshold
                        # because freePercentage < minFreePercentage at this point
                        numberOfUserToBan = int((self.maxFreePercentage - freePercentage) * totalUser)
                        if numberOfUserToBan <= 0:
                            enforcer.logger.warning("The maximum free threshold is not high enough, no user will be banned.")
                        else :
                            # in case we don't have enough users to ban
                            numberOfUserToBan = min(numberOfUserToBan, len(self.bannedUsers))
                            self.bannedUsers = self.bannedUsers[:numberOfUserToBan]
                            enforcer.getService('notifyEvent').execute(self.bannedUsers, UserEvent.BAN)
                            enforcer.getService('writeFlexOptFile').execute(FlexLmManager.generateDenyGroup([oUser.getUid() for oUser in self.bannedUsers]))
                    else:
                        enforcer.logger.warning("License server is nearly full, but no user can be banned...")


                elif self.idealState == ApplicationState.FREE:
                    enforcer.logger.info("Switched to  ApplicationState.FREE")

                if not enforcer.getService('scheduleServerReloadOnce').execute():
                    enforcer.logger.info("Server restart already scheduled");

                self.currentState = self.idealState
                self.switchTime = self.when
            else:
                if self.currentState == ApplicationState.DENY:
                    cs = "DENY"
                elif self.currentState == ApplicationState.FREE:
                    cs = "FREE"
                enforcer.logger.info("Keep at state '%s', last switch at %s", cs, self.switchTime)
            # end if self.switchTime
        else:
            enforcer.logger.info("Switch not permitted yet, keep at state %s (last switch at %s)", self.currentState, self.switchTime)

    def cleanup(self, enforcer):
        enforcer.getService('writeFlexOptFile').execute()
        if len(self.bannedUsers) > 0 :
            enforcer.getService('notifyEvent').execute(self.bannedUsers, UserEvent.UNBAN)
        self.bannedUsers = []
        if self.idealState != ApplicationState.FREE:
            enforcer.getService('scheduleServerReloadOnce')

    def unBanUsers(self, enforcer):
        """Unban (restore the original flex opt file and notifies users) users"""
        enforcer.getService('writeFlexOptFile').execute()
        for user in self.bannedUsers:
            enforcer.getService('resetUserUsage').execute(user, self.when)
        enforcer.getService('notifyEvent').execute(copy.copy(self.bannedUsers), UserEvent.UNBAN)
        self.bannedUsers = []

    def getCurrentState(self):
        return self.currentState

    def getCurrentIdealState(self):
        return self.idealState

class WarnUsersBeforeMaxUsageTimeStrategy(ManagementStrategy):
    """Strategy that warns users that have been logged on for too long when the number of free
    licenses reaches a given threshold"""

    def __init__(self, warnThreshold, warnDelay = 0):
        """Create a new warning strategy
        warnThreshold - Threshold at which the users should be warned
        warnDelay - user will be warned warnDelay before maximum usage time
        
        """
        ManagementStrategy.__init__(self)
        self.warnedUsersNum = 0
        self.warnThreshold = warnThreshold
        self.warnDelay = warnDelay
        self.requiredServices = ['notifyEvent', 'getFreePercentage', 'getUserBeforeMaxUsage']

    def strategy(self, enforcer):
        if enforcer.getService('getFreePercentage').execute() < self.warnThreshold:
            toWarnUsers = enforcer.getService('getUserBeforeMaxUsage').execute(self.warnDelay)
            if len(toWarnUsers) > 0:
                enforcer.getService('notifyEvent').execute(toWarnUsers, UserEvent.WARN)
                self.warnedUsersNum += len(toWarnUsers)
            else :
                enforcer.logger.warn("Warning threshold reached but no user needs warning")
