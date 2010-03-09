# Deadline the #UvA IRC Bot

import os

# Verify we are not on Windows (NTKRN)
if os.name == 'nt':
	print """Sorry, Deadline is not supported on Windows
due to their implementation of the POSIX select() function"""
	exit(1)

# Import all required stuff
from deadline import *
import sys
import locale
from errno import EINTR
import select

# Global settings variables
keep_running = True

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
locale.setlocale(locale.LC_ALL, '')

# Das Entrypoint
def main():
	global ircc
	mainwin = gui.getMainWindow()
	mainwin.setTitle("Deadline v0.1")
	mainwin.setTitleAlignment(TITLE_MODE_CENTERED)
	mainwin.addNotice("Welcome to Deadline v0.1")
	mainwin.addNotice("You can type '/quit' to quit," +
		" or type something else to simply see it" +
		" show up in this window :-)")

	# Do debug connect to IRC Freenode
	mainwin.addNotice("Looking up irc.freenode.net")
	gui.show()
	ircc = YeOldeIRCClient('irc.freenode.net')
	ircs = ircc.getSocket()
	mainwin.addNotice("Connecting to irc.freenode.net")
	gui.redrawFromScratch()

	while keep_running:
		try:
			if ircc.isConnected():
				select.select([sys.stdin, ircs], [], [])
			else:
				select.select([sys.stdin], [ircs], [])
				ircc.doConnect()
		except select.error, e:
			if e.args[0] == EINTR:
				# We might've been interrupted by a SIGWINCH
				# signal, which means we need to resize our
				# window
				gui.stdscr.touchwin()
			else:
				raise e
		while gui.inputEvent():
			pass

		# Lame ass loop for IRC Chat
		while True:
			ircc.handleSend()
			x = ircc.recvCommand()
			if x is None:
				break
			mainwin.addIncoming(x)
		gui.redrawFromScratch()

gui = DeadGUI()
try:
	main()
finally:
	gui.hide()
print "Have a nice day!"

