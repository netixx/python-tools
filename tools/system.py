'''Module providing a shell interface to execute commands as well as other environment related features

'''

__all__ = ['Console', 'DirectoryManager']

from subprocess import Popen, PIPE
import re

class Console(object):
    """
    Object to send commands to the shell (in a subprocess)
    """
    @staticmethod
    def sendCommand(command, sendExtraLine = False):
        """Sends a command to the console
        returns an object representing the result
        an extra line is sent if required, eg because of mks neck message
        
        """
        proc = Popen(command, shell = True, stdin = PIPE, stderr = PIPE, stdout = PIPE)
        if sendExtraLine:
            proc.stdin.write('\n')
        resOut = proc.stdout.read()
        resErr = proc.stderr.read()

        proc.stdin.close()
        returnCode = proc.wait()

        proc.stdout.close()
        proc.stderr.close()

        return Console.Result(returnCode, resOut, resErr)

    class Result(object):
        """Represents a Result from a command"""
        def __init__(self, returnCode, result, errors):
            self.__returnCode = returnCode
            self.__result = result
            self.__errors = errors

        def getReturnCode(self):
            return self.__returnCode

        def getResult(self):
            return self.__result

        def getErrors(self):
            if self.hasErrors() and (self.__errors is None or self.__errors == ""):
                return self.__result
            return self.__errors

        def hasErrors(self):
            return self.__returnCode != 0 or self.__errors != ""

        def getSplitResult(self):
            return self.getResult().splitlines()


class DirectoryManager(object):
    """Class to query the windows directory service"""
    @staticmethod
    def getUserEmailByUid(uid):
        """Get the user email (registered as upn...) from the windows directory
        
        uid - the windows user name
        
        """
        command = "dsquery user -samid %s | dsget user -L -upn" % uid
        ret = Console.sendCommand(command, False)
        if ret.getReturnCode() != 0:
            return None
        ret = ret.getSplitResult()
        pattern = re.compile(r"\s*upn:\s*([^\s]+)")
        for singleLine in ret:
            lineMatch = pattern.match(singleLine)
            if lineMatch != None:
                return lineMatch.group(1)

        return None

