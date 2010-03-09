# Deadline IRC library
import socket
import errno

# Currently IPv4 only
class YeOldeIRCClient(object):
	def __init__(self, servername):
		self.server = servername

		# Connection settings
		self.connected = False
		self.ip = None
		self.sock = None
		self.doConnect()

		# Transfer settings
		self.sendbuf = ''
		self.recvbuf = ''

	def doConnect(self):
		if self.connected:
			return False
		if self.ip is None:
			self.ip = socket.gethostbyname(self.server)
		if self.sock is None:
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sock.setblocking(0)
		try:
			if self.sock.connect((self.ip, 6667)) is None:
				self.connected = True
		except socket.error, e:
			if e.errno != errno.EINPROGRESS:
				raise e
		return True

	def isConnected(self):
		self.handleRecv()
		return self.connected

	def getSocket(self):
		return self.sock

	def handleSend(self):
		if not self.connected:
			return False
		if len(self.sendbuf):
			try:
				x = self.sock.send(self.sendbuf)
				self.sendbuf = self.sendbuf[x:]
				return True
			except socket.error, e:
				if e.errno != errno.EWOULDBLOCK:
					raise e
				return True
		return False

	def sendCommand(self, data):
		self.sendbuf += data + "\r\n"
		return self.handleSend()

	def handleRecv(self):
		if not self.connected:
			return False
		try:
			x = self.sock.recv(4096)
		except socket.error, e:
			if e.errno != errno.EWOULDBLOCK:
				raise e
			return False
		if not len(x):
			self.sock.close()
			del self.sock
			self.sock = None
			self.connected = False
			return False
		self.recvbuf += x
		return True

	def recvCommand(self):
		self.handleRecv()
		i = self.recvbuf.find('\r\n')
		if i >= 0:
			com = self.recvbuf[:i]
			self.recvbuf = self.recvbuf[i + 2:]
			return com
		return None

