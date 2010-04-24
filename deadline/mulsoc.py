# mulsoc.py - Socket Multiplexer
"""
    The non-blocking sockets library

    This library provides a straight forward implementation of non-blocking
    sockets, designed to be used in an event driven application.
"""

import socket
from select import select, error as select_error
from time import time
import errno
from events import DeadEventQueue, DeferredCall

def getMyIP():
    return socket.gethostbyname(socket.gethostname())

class SocketMultiplexer(object):
    """
        Abstract socket multiplexer, useful for managing lots of sockets
        with a single thread.
        Inherit to create a multiplexed socket based application.
        You should only override the on***() callback methods.
    """

    # Setup optimized listen queue default
    # The maximum should be 128 by default under linux 2.0 and up
    # To check do a 'cat /proc/sys/net/core/somaxconn'
    LISTEN_QUEUE_MAXIMUM = socket.SOMAXCONN
    LISTEN_QUEUE_DEFAULT = min(16, socket.SOMAXCONN)

    class Deadlock(Exception):
        """
            This class represents the occurrence of a deadlock in the event
            processing system. (It would wait forever on nothing)
        """

    def __init__(self, sock = None):
        """
            Initialize a base SocketMultiplexer that uses 'sock' as its
            ManagedSocket instantiator.
        """
        self._keep_running = False
        if sock is None:
            sock = ManagedSocket
        self._sock = sock
        self.eq = DeadEventQueue()
        self._alarm = None
        self._reads, self._writes = [], []

    def startMultiplex(self):
        """
            Begin multiplexing non-blocking sockets.
            This call does not return, until either a deadlock exception occurs
            or stopMultiplex is called.
        """

        self._keep_running = True
        tick = None

        while self._keep_running:
            try:

                # Handle the events system
                if self.eq.nextEventTicks() is None:
                    tick = None
                elif tick is None:
                    tick = time()
                else:
                    newtick = time()
                    if newtick - tick > 0.0:
                        self.eq.elapseTime(newtick - tick)
                    tick = newtick
                    del newtick

                # Guard against activity deadlocks
                # They really shouldn't occur, but it is good practice to
                # catch them.
                if len(self._reads) + len(self._writes) == 0 and \
                        self.eq.nextEventTicks() is None:
                    raise SocketMultiplexer.Deadlock("No events left")

                # Wait for activity
                reads, writes, excepts = \
                    select(self._reads, self._writes, [],
                        self.eq.nextEventTicks())

                # Handle the events system
                # I know this isn't the nicest solution, but
                # this is required to fix a nasty bug triggering over
                # execution.
                if self.eq.nextEventTicks() is None:
                    tick = None
                elif tick is None:
                    tick = time()
                else:
                    newtick = time()
                    if newtick - tick > 0.0:
                        self.eq.elapseTime(newtick - tick)
                    tick = newtick
                    del newtick

            except select_error, e:
                if e.args[0] == errno.EINTR:
                    self.onSignal()
                    continue
                self._keep_running = False
                raise e

            # Handle reads and writes
            for r in reads: r.handleRead()
            for w in writes: w.handleWrite()

        return True

    def timeFlow(self):
        """
            Executes the flow of time.

            This function will be used in the future to
            prevent clock jumps and streamline the events system.
        """

    def stopMultiplex(self):
        """
            Stop multiplexing.
        """
        if not self._keep_running:
            return False
        self._keep_running = False
        return True

    def connect(self, ip, port, **keywords):
        """
            Initiate a client connection to the specified server.

            Additionally you can specify 'sock = <some class' in the
            function call to override the default socket instantiator.
            Any additional keywords shall be passed on to
            the socket constructor.
        """
        try:
            sock = keywords['sock']
            del keywords['sock']
        except KeyError:
            sock = self._sock
        new = sock(self, ip, port, **keywords)
        new.connect()
        return True

    def listen(self, ip, port,
            queue_length = None, **keywords):
        """
            Create a new socket that will start listening on
            the specified address.

            Additionally you can specify 'sock = <some class' in the
            function call to override the default socket instantiator.
            Any additional keywords shall be passed on to
            the socket constructor.
        """
        if queue_length == None:
            queue_length = SocketMultiplexer.LISTEN_QUEUE_DEFAULT
        try:
            sock = keywords['sock']
            del keywords['sock']
        except KeyError:
            sock = self._sock
        new = sock(self, ip, port, **keywords)
        new = self._sock(self, ip, port)
        if not new.listen(queue_length):
            return False
        return True

    def addReader(self, sock):
        """
            Add socket to the list of sockets watched for reading
        """
        if sock in self._reads:
            return False
        self._reads.append(sock)
        return True

    def delReader(self, sock):
        """
            Delete socket from the list of sockets watched for reading
        """
        try:
            self._reads.remove(sock)
        except AttributeError:
            return False
        return True

    def addWriter(self, sock):
        """
            Add socket to the list of sockets watched for writing
        """
        if sock in self._writes:
            return False
        self._writes.append(sock)
        return True

    def delWriter(self, sock):
        """
            Delete socket from the list of sockets watched for writing
        """
        try:
            self._writes.remove(sock)
        except AttributeError:
            return False
        return True

    def setAlarm(self, seconds):
        """
            Sets an alarm that will occur in 'seconds' time, seconds may be
            fractional. If seconds is None any pending alarm will be cancelled
        """

        if self._alarm is not None:
            self.eq.cancelEvent(self._alarm)
        if seconds is not None:
            self._alarm = DeferredCall(seconds, self.execAlarm)
            self.eq.scheduleEvent(self._alarm)
        return True

    def execAlarm(self):
        """
            Handler that executes the onAlarm() method.
        """
        self._alarm = None
        self.onAlarm()

    def onAlarm(self):
        """
            Called when the alarm set by setAlarm() occurs
        """

    def onSignal(self):
        """
            Called when select() is interrupted by a signal.
        """

class ManagedSocket(object):
    """
        This class represents a managed non-blocking socket.
        Inherit this class for managing connection specific states the easy way.
        You should only override the on***() callback methods.
    """
    WATCH_READ, WATCH_WRITE = [1, 2]
    UNBOUND, CONNECTING, CONNECTED, DISCONNECTED, LISTENING, CLOSED = range(6)

    def __init__(self, muxer, ip, port):
        """
            Instantiate an abstract managed socket.

            This method can be called in 2 ways:
                the expected way, a muxer, an ip, and a port, or

                the unexpected way, re-using an already connected socket
                (that has been obtained through accepting).
                In this case 'port' should contain a tuple describing
                the peer's address (ip, port).
                'ip' should contain a tuple containing only the socket object.
        """

        if type(ip) is tuple:
            self._sock = ip[0]
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.ip, self.port = port
            self._state = ManagedSocket.CONNECTED
            muxer.addReader(self)
        else:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.ip = ip
            self.port = port
            self._state = ManagedSocket.UNBOUND

        # Setup common states
        self._sock.setblocking(0)
        self.muxer = muxer
        self._wbuf = ''

        # Last write blocked flag, used for speeding up non-blocking writes
        self._lwb = False

    def fileno(self):
        """
            Return this socket's file descriptor for waiting.
        """
        return self._sock.fileno()

    def listen(self, queue_length):
        """
            Start listening for clients.
        """
        if self._state != ManagedSocket.UNBOUND:
            return False
        try:
            self._sock.bind((self.ip, self.port))
        except socket.error, e:
            error = e.args[0]
            if error != errno.EADDRINUSE and error != errno.EACCES:
                raise e
            return False
        self._state = ManagedSocket.DISCONNECTED
        self._sock.listen(queue_length)
        self.muxer.addReader(self)
        self._state = ManagedSocket.LISTENING
        return True

    def connect(self):
        """
            Start connecting to client.
        """

        if self._state != ManagedSocket.UNBOUND:
            return False
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.handleConnect()

        return self._state != ManagedSocket.DISCONNECTED

    def handleConnect(self):
        """
            Function negotiating a non-blocked connect, this is for internal
            use only.
        """

        if self._state == ManagedSocket.CONNECTED:
            return False

        if self._state != ManagedSocket.CONNECTING:
            self._state = ManagedSocket.CONNECTING
            self.muxer.addWriter(self)

        try:
            self._sock.connect((self.ip, self.port))
            self._state = ManagedSocket.CONNECTED
            self.onConnect()
            self.muxer.addReader(self)
            self.muxer.delWriter(self)
        except socket.error, e:
            error = e.args[0]
            if error == errno.ECONNREFUSED or error == errno.ETIMEDOUT:
                self._state = ManagedSocket.DISCONNECTED
                self.muxer.delWriter(self)
                self.onConnectionRefuse()
                return False
            elif error == errno.EAGAIN:
                return False
            elif error != errno.EINPROGRESS:
                raise e
        return True

    def handleRead(self):
        """
            Internal function that mediates non-blocking reads.
        """

        # Read data
        data = ''
        d = ''
        if self._state == ManagedSocket.CONNECTED:
            try:
                while self._state == ManagedSocket.CONNECTED:
                    d = self._sock.recv(4096)
                    if d == '':
                        break
                    data += d
            except socket.error, e:
                error = e.args[0]
                if error == errno.ECONNRESET or error == errno.ETIMEDOUT:
                    self.muxer.delReader(self)
                    if self._lwb:
                        self.muxer.delWriter(self)
                    self._state = ManagedSocket.DISCONNECTED
                    self.onDisconnect()
                elif error != errno.EWOULDBLOCK and error != errno.EINTR:
                    raise e

            if data != '':
                self.onRecv(data)

            # Connection lost or shutdown
            if d =='' and self._state == ManagedSocket.CONNECTED:
                self.muxer.delReader(self)
                if self._lwb:
                    self.muxer.delWriter(self)
                self._state = ManagedSocket.DISCONNECTED
                self.onDisconnect()
            return True

        # Accept a new client
        elif self._state == ManagedSocket.LISTENING:
            try:
                while self._state == ManagedSocket.LISTENING:
                    conn, addr = self._sock.accept()
                    self.onAccept(type(self)(self.muxer, (conn,), addr))
            except socket.error, e:
                error = e.args[0]
                if error != errno.EWOULDBLOCK and error != errno.EINTR:
                    raise e

            return True

        return False

    def handleWrite(self):
        """
            Internal function that mediates non-blocking writes.
        """

        if self._state == ManagedSocket.CONNECTING:
            self.handleConnect()
            return True
        elif self._state != ManagedSocket.CONNECTED:
            return False

        while len(self._wbuf) and self._state == ManagedSocket.CONNECTED:
            try:
                x = self._sock.send(self._wbuf[:4096])
                self._wbuf = self._wbuf[x:]
            except socket.error, e:
                error = e.args[0]

                # Connection lost
                if error == errno.EPIPE or error == errno.ECONNRESET \
                    or error == errno.ETIMEDOUT:
                    self._state = ManagedSocket.DISCONNECTED
                    self.muxer.delReader(self)
                    if self._lwb:
                        self.muxer.delWriter(self)
                    self.onDisconnect()
                    self._wbuf = ''
                    return False
                elif error == errno.EWOULDBLOCK:
                    if not self._lwb:
                        self._lwb = True
                        self.muxer.addWriter(self)
                elif error != errno.EINTR:
                    raise e
                break

        if not len(self._wbuf) and self._lwb:
            self.muxer.delWriter(self)

        return True

    def send(self, data):
        """
            Place data in the output buffer for sending. All data will be
            sent ASAP to the peer socket.
        """
        if self._state != ManagedSocket.CONNECTED:
            return False
        self._wbuf += data
        self.handleWrite()
        return True

    def close(self):
        """
            Close socket, you should delete this socket after closing, it will
            not be of any more worth.
        """

        if self._state == ManagedSocket.CLOSED:
            return False

        if self._state == ManagedSocket.CONNECTED:

            # There are some rare conditions in which our socket has become
            # disconnected before executing this call
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except socket.error, e:
                error = e.args[0]
                if error != ENOTCONN:
                    raise e

            self.muxer.delReader(self)
            if self._lwb:
                self.muxer.delWriter(self)
        elif self._state == ManagedSocket.CONNECTING:
            self.muxer.delWriter(self)
        elif self._state == ManagedSocket.LISTENING:
            self.muxer.delReader(self)

        self._sock.close()
        self._sock = None
        self._state = ManagedSocket.CLOSED
        return True

    def onRecv(self, data):
        """
            This callback is called on incoming data.
        """

    def onDisconnect(self):
        """
            Called when the connection is lost or when the other sockets closes.
        """

    def onConnectionRefuse(self):
        """
            Called when a pending connection is refused by the server.
        """

    def onConnect(self):
        """
            Called when successfully connected to a server.
        """

    def onAccept(self, sock):
        """
            Called whenever a new client is accepted on a socket that was
            listening. 'sock' is the accepted socket.
        """

