# Deadline the #UvA IRC Bot

import os

# Verify we are not on Windows (NTKRN)
if os.name == 'nt':
	print """Sorry, Deadline is not supported on Windows
due to their implementation of the POSIX select() function"""
	exit(1)

# Import all required stuff
from __init__ import *
import sys
from errno import EINTR
from time import time, localtime
import select

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
import locale
locale.setlocale(locale.LC_ALL, '')

class Deadline(SocketMultiplexer):
	"""
		Deadline IRC bot v0.1

		Application class
	"""

	def __init__(self):
		SocketMultiplexer.__init__(self)
		self.addReader(StandardInput())

	# Das Entrypoint
	def run(self):
		# Setup prompt commands
		gui.registerCommand('quit', self.quitCall)
		gui.registerCommand('connect', self.connectCall)

		# Initialize main window
		mainwin = gui.getMainWindow()
		mainwin.setTitle("Deadline v0.1")
		mainwin.setTitleAlignment(TITLE_MODE_CENTERED)
		mainwin.addNotice("Welcome to Deadline v0.1")
		mainwin.addNotice("You can type '/quit' to quit," +
			" or type something else to simply see it" +
			" show up in this window :-)")
		gui.show()
		self.startMultiplex()

	def onSignal(self):
		"""
			Handles SIGWINCH for terminal resizing.
		"""
		gui.stdscr.touchwin()

	def quitCall(self, str):
		self.stopMultiplex()

	def connectCall(self, server):
		pass

class StandardInput(object):
	"""
		Standard input handler for SocketMultiplexer
	"""

	def fileno(self):
		return sys.stdin.fileno()

	def handleRead(self):
		while gui.inputEvent():
			pass

gui = DeadGUI()
app = Deadline()

try:
	app.run()
finally:
	gui.hide()
print "Have a nice day!"

