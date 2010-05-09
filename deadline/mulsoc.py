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
		self.keep_running = False
		if sock is None:
			sock = ManagedSocket
		self.sock = sock
		self.eq = DeadEventQueue()
		self.reads, self.writes = [], []

	def startMultiplex(self):
		"""
			Begin multiplexing non-blocking sockets.
			This call does not return, until either a deadlock exception occurs
			or stopMultiplex is called.
		"""

		self.keep_running = True
		tick = None

		while self.keep_running:
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
				if len(self.reads) + len(self.writes) == 0 and \
						self.eq.nextEventTicks() is None:
					raise SocketMultiplexer.Deadlock("No events left")

				# Wait for activity
				reads, writes, excepts = \
					select(self.reads, self.writes, [],
						self.eq.nextEventTicks())

			except select_error, e:
				if e.args[0] == errno.EINTR:
					self.onSignal()
					continue
				self.keep_running = False
				raise e

			# Handle reads and writes
			for r in reads: r.handleRead()
			for w in writes: w.handleWrite()

		return True

	def stopMultiplex(self):
		"""
			Stop multiplexing.
		"""
		if not self.keep_running:
			return False
		self.keep_running = False
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
			sock = self.sock
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
			sock = self.sock
		new = sock(self, ip, port, **keywords)
		new = self.sock(self, ip, port)
		if not new.listen(queue_length):
			return False
		return True

	def addReader(self, sock):
		"""
			Add socket to the list of sockets watched for reading
		"""
		if sock in self.reads:
			return False
		self.reads.append(sock)
		return True

	def delReader(self, sock):
		"""
			Delete socket from the list of sockets watched for reading
		"""
		try:
			self.reads.remove(sock)
		except NoSuchElementException:
			return False
		return True

	def addWriter(self, sock):
		"""
			Add socket to the list of sockets watched for writing
		"""
		if sock in self.writes:
			return False
		self.writes.append(sock)
		return True

	def delWriter(self, sock):
		"""
			Delete socket from the list of sockets watched for writing
		"""
		try:
			self.writes.remove(sock)
		except NoSuchElementException:
			return False
		return True

	def setAlarm(self, seconds):
		"""
			Sets an alarm that will occur in 'seconds' time, seconds may be
			fractional. If seconds is None any pending alarm will be cancelled
		"""

		if self.alarm is not None:
			self.eq.cancelEvent(self.alarm)
		self.alarm = DeferredCall(seconds, self.execAlarm)
		self.eq.scheduleEvent(self.alarm)
		return True

	def execAlarm(self):
		"""
			Handler that executes the onAlarm() method.
		"""
		self.alarm = None
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
				In this case 'port' should contain a tupple describing
				the peer's address (ip, port).
		"""

		if type(ip) is socket.socket:
			self.sock = ip
			self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
			self.ip, self.port = port
			self.state = ManagedSocket.CONNECTED
			muxer.addReader(self)
		else:
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.ip = ip
			self.port = port
			self.state = ManagedSocket.UNBOUND

		# Setup common states
		self.sock.setblocking(0)
		self.muxer = muxer
		self.wbuf = ''

		# Last write blocked flag, used for speeding up non-blocking writes
		self.lwb = False

	def fileno(self):
		"""
			Return this socket's file descriptor for waiting.
		"""
		return self.sock.fileno()

	def listen(self, queue_length):
		"""
			Start listening for clients.
		"""
		if self.state != ManagedSocket.UNBOUND:
			return False
		self.sock.bind((self.ip, self.port))
		self.state = ManagedSocket.DISCONNECTED
		try:
			self.sock.listen(queue_length)
		except socket.error, e:
			error = e.args[0]
			if error != EADDRINUSE:
				raise e
			return False
		self.muxer.addReader(self)
		self.state = ManagedSocket.LISTENING
		return True

	def connect(self):
		"""
			Start connecting to client.
		"""

		if self.state != ManagedSocket.UNBOUND:
			return False
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		self.handleConnect()

		return self.state != ManagedSocket.DISCONNECTED

	def handleConnect(self):
		"""
			Function negotiating a non-blocked connect, this is for internal
			use only.
		"""

		if self.state == ManagedSocket.CONNECTED:
			return False

		if self.state != ManagedSocket.CONNECTING:
			self.state = ManagedSocket.CONNECTING
			self.muxer.addWriter(self)

		try:
			self.sock.connect((self.ip, self.port))
			self.state = ManagedSocket.CONNECTED
			self.onConnect()
			self.muxer.addReader(self)
			self.muxer.delWriter(self)
		except socket.error, e:
			error = e.args[0]
			if error == errno.ECONNREFUSED:
				self.state = ManagedSocket.DISCONNECTED
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
		if self.state == ManagedSocket.CONNECTED:
			try:
				while self.state == ManagedSocket.CONNECTED:
					d = self.sock.recv(4096)
					if d == '':
						break
					data += d
			except socket.error, e:
				error = e.args[0]
				if error != errno.EWOULDBLOCK and error != errno.EINTR:
					raise e

			if data != '':
				self.onRecv(data)

			# Connection lost or shutdown
			if d == '':
				self.state = ManagedSocket.DISCONNECTED
				self.onDisconnect()
			return True

		# Accept a new client
		elif self.state == ManagedSocket.LISTENING:
			try:
				while self.state == ManagedSocket.LISTENING:
					conn, addr = self.sock.accept()
					self.onAccept(type(self)(self.muxer, conn, addr))
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

		if self.state == ManagedSocket.CONNECTING:
			self.handleConnect()
			return True
		elif self.state != ManagedSocket.CONNECTED:
			return False

		while len(self.wbuf) and self.state == ManagedSocket.CONNECTED:
			try:
				x = self.sock.send(self.wbuf[:4096])
				self.wbuf = self.wbuf[x:]
			except socket.error, e:
				error = e.args[0]

				# Connection lost
				if error == errno.EPIPE:
					self.state = ManagedSocket.DISCONNECTED
					self.onDisconnect()
					self.wbuf = ''
				elif error == errno.EWOULDBLOCK:
					if not self.lwb:
						self.lwb = True
						self.muxer.addWriter(self)
				elif error != errno.EINTR:
					raise e
				break

		if not len(self.wbuf) and self.lwb:
			self.muxer.delWriter(self)

		return True

	def send(self, data):
		"""
			Place data in the output buffer for sending. All data will be
			sent ASAP to the peer socket.
		"""
		if self.state != ManagedSocket.CONNECTED:
			return False
		self.wbuf += data
		self.handleWrite()
		return True

	def close(self):
		"""
			Close socket, you should delete this socket after closing, it will
			not be of any more worth.
		"""

		if self.state == ManagedSocket.CLOSED:
			return False

		if self.state == ManagedSocket.CONNECTED:

			# There are some rare conditions in which our socket has become
			# disconnected before executing this call
			try:
				self.sock.shutdown(socket.SHUT_RDWR)
			except socket.error, e:
				error = e.args[0]
				if error != ENOTCONN:
					raise e

			self.muxer.delReader(self)
			if self.lwb:
				self.muxer.delWriter(self)
		elif self.state == ManagedSocket.CONNECTING:
			self.muxer.delWriter(self)
		elif self.state == ManagedSocket.LISTENING:
			self.muxer.delReader(self)

		self.sock.close()
		self.sock = None
		self.state = ManagedSocket.CLOSED
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

