'''Module to communicate things to whoever with whatever channel

Currently implemented channels are mail, ...

@author: sbx1756

'''
__all__ = ['Mailer']

from threading import Thread
from queue import Queue
from email.message import Message
from smtplib import SMTP, SMTPServerDisconnected
import socket
import logging

class Mailer(Thread):
    """Sends mail via SMTP (in another thread)
    Connection is reestablished for each mail (connection drops otherwise)
    Waits for mails to arrive in the queue and sends them
    
    Writes logs to a file unless specified by in configuration
    
    There can be multiple instances of this class, they should be created (and accessed) 
    via the getMailer() method which always returns the same instance of the mailer
    
    """

    mailerPool = {}

    @classmethod
    def getMailer(cls, name, configuration = None):
        """Get a mailer by name , creating it if 
        if does not exists, using the provided configuration
        
        """
        if cls.mailerPool.has_key(name):
            return cls.mailerPool[name]

        cls.mailerPool[name] = Mailer(configuration, name = "%s_%s" % (name, len(cls.mailerPool)))
        return cls.mailerPool[name]

    def __init__(self, configuration, name, mailQueue = Queue()):
        """Create a new mailer instance
        
        configuration - an instance of Mailer.Configuration
        name - the name of the thread for this mailer
        mailQueue - use this if you want to share a queue between multiple mailers
        
        """
        Thread.__init__(self)
        self.setName("Mailer-%s" % name)
        self.isRunning = True
        self.transport = None
        assert isinstance(configuration, Mailer.Configuration)
        self.config = configuration
        self.logger = configuration.getLogger()
        assert isinstance(mailQueue, Queue)
        self.mailQueue = mailQueue

    def queueMail(self, mail):
        """Queue a new mail"""
        if mail is not None:
            assert isinstance(mail, Message)
            self.mailQueue.put(mail)

    def sendMail(self, mail):
        """Sends an Email"""
        if self.config.doSend():
            try :
                self.logger.debug("Trying to send mail : '%s' to user %s", mail['Subject'], mail['To'])
                mail['From'] = "%s <%s>" % (self.config.getFromName(), self.config.getFromAddr())
                # TODO : put a timeout ?
                self.transport = SMTP(host = self.config.getHost(), port = self.config.getPort(), timeout = self.config.getConnectionTimeout())
                if self.config.isMock():
                    self.transport.sendmail(self.config.getFromAddr(), ["francois.espinet@valeo.com", "rudolf.widmann@valeo.com"], mail.as_string())
                else :
                    self.transport.sendmail(self.config.getFromAddr(), mail["To"], mail.as_string())

                self.logger.info("Mail sent to : %s", mail['To'])
            except Exception as e :
                self.logger.warning("Error while sending mail : %s", e)
            finally:
                if self.transport is not None :
                    self.transport.quit()

        else:
            self.logger.debug("Application parameter mail is %s, mail not sent : \n %s", self.config.doSend(), mail.as_string())
        self.mailQueue.task_done()

    def run(self):
        self.logger.info("Mailer started")
        while self.isRunning:
            mail = self.mailQueue.get()
            if mail is not None :
                self.logger.debug("Got a new mail to send")
                try :
                    self.sendMail(mail)
                except Exception as e:
                    self.logger.critical("A exception occured while sending an email : %s", e)
            else:
                self.isRunning = False
                self.mailQueue.task_done()

    def terminate(self):
        """Wait for all mail to be sent before termination"""
        self.mailQueue.put(None)
        self.mailQueue.join()
        self.join()
        self.logger.info("Mailer terminated")


    class Configuration(object):
        """Configuration information for the mailer"""

        DEFAULT_FROM_NAME = "Script management"
        DEFAULT_SMTP_HOST = "BIE2-smtpserver.vnet.valeo.com"
        DEFAULT_SMTP_PORT = 25
        DEFAULT_SMTP_TIMEOUT = socket._GLOBAL_DEFAULT_TIMEOUT
        DEFAULT_ADMIN_ADDRS = ["rudolf.widmann@valeo.com"]

        def __init__(self,
                     fromAddr,
                     fromName = None,
                     smtpHost = None,
                     smtpPort = None,
                     smtpTimeout = None,
                     adminAddrs = None,
                     mock = False,
                     sendMails = True,
                     actionLogger = None):
            """Create a new Configuration
            
            fromAddr - the address to use in the From field of the mail and for the smtp FROM parameter
            fromName - the Name to use in the From field of the mail
            smtpHost - the address of the SMTP server
            smtpPort - port of the smtp server
            smtpTimeout - timeout for the smtp connection
            adminAddrs - addresses of the administrators of the script
            mock - should the mailer run in mock mode (mails are send to the admin instead of users)
            sendMails - should mails actually be send
            actionLogger - an instance of a logger, if None, root logger is used
            
            """
            fromName = self.DEFAULT_FROM_NAME
            smtpHost = self.DEFAULT_SMTP_HOST
            smtpPort = self.DEFAULT_SMTP_PORT
            smtpTimeout = self.DEFAULT_SMTP_TIMEOUT
            adminAddrs = self.DEFAULT_ADMIN_ADDRS

            self.__fromAddrs = fromAddr
            self.__fromName = fromName
            self.__smtpHost = smtpHost
            self.__smtpPort = smtpPort
            self.__adminAddrs = adminAddrs
            self.__mock = mock
            self.__sendMails = sendMails
            self.__actionLogger = actionLogger
            if self.__actionLogger is None:
                self.__actionLogger = logging.getLogger()
            self.__smtpTimeout = smtpTimeout


        def getFromAddr(self):
            return self.__fromAddrs

        def getFromName(self):
            return self.__fromName

        def getHost(self):
            return self.__smtpHost

        def getPort(self):
            return self.__smtpPort

        def getConnectionTimeout(self):
            self.__smtpTimeout

        def getAdminAddrs(self):
            return self.__adminAddrs

        def isMock(self):
            return self.__mock

        def doSend(self):
            return self.__sendMails

        def doLog(self):
            return self.__actionLogger is not None

        def getLogger(self):
            return self.__actionLogger


