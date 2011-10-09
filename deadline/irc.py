# Deadline IRC library
import socket
import errno

from mulsoc import ManagedSocket, DeferredCall

# Currently IPv4 only
class YeOldeIRCClient(ManagedSocket):
    def onConnect(self):
        self.muxer.eq.scheduleEvent(DeferredCall(2.5, self.sendOpening))
        self.muxer.msock = self
        self.stream = ''

    def sendOpening(self):
        self.sendRaw('USER deadline * 8: Deadline IRC')
        self.sendRaw('NICK hoi')
        self.muxer.eq.scheduleEvent(DeferredCall(3.0, self.sendJoin,
            channel = '#deadline'))

    def sendRaw(self, cmd):
        self.send(cmd + '\r\n')
        self.muxer.debugSendRaw(cmd)

    def onRecv(self, data):
        self.stream += data
        i = self.stream.find('\r\n')
        while i > -1:
            cmd = self.stream[:i]
            self.stream = self.stream[i + 2:]
            self.onRecvRaw(cmd)
            i = self.stream.find('\r\n')

    def onRecvRaw(self, cmd):
        self.muxer.debugRecvRaw(cmd)

    def sendJoin(self, channel):
        self.sendRaw('JOIN :%s' % channel)

