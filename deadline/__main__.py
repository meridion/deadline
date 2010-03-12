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

# Global settings variables
keep_running = True

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
import locale
locale.setlocale(locale.LC_ALL, '')

# Das Entrypoint
def main():
	# Setup prompt commands
	gui.registerCommand('quit', quitCall)
	gui.registerCommand('connect', connectCall)

	# Initialize main window
	mainwin = gui.getMainWindow()
	mainwin.setTitle("Deadline v0.1")
	mainwin.setTitleAlignment(TITLE_MODE_CENTERED)
	mainwin.addNotice("Welcome to Deadline v0.1")
	mainwin.addNotice("You can type '/quit' to quit," +
		" or type something else to simply see it" +
		" show up in this window :-)")
	gui.show()

	# Setup Event queue
	newclock = clock = time()
	eq = DeadEventQueue()
	eq.scheduleEvent(TestEvent(testEvent))

	while keep_running:
		try:
			# if ircc.isConnected():
			# 	select.select([sys.stdin, ircs], [], [])
			# else:
			# 	select.select([sys.stdin], [ircs], [])
			# 	ircc.doConnect()
			if newclock - clock > 0.0:
				eq.elapseTime(newclock - clock)
			clock = newclock
			rl, wl, el = select.select([sys.stdin], [], [], eq.nextEventTicks())
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
		newclock = time()

def quitCall(str):
	global keep_running
	keep_running = False

def connectCall(server):
	pass

def testEvent():
	gui.getMainWindow().addNotice("Test event occurred")
	gui.redrawFromScratch()

gui = DeadGUI()
try:
	main()
finally:
	gui.hide()
print "Have a nice day!"

