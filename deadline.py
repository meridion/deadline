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
from errno import EINTR
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
	gui.registerCommand('quit', quitEvent)
	gui.registerCommand('connect', connectEvent)

	# Initialize main window
	mainwin = gui.getMainWindow()
	mainwin.setTitle("Deadline v0.1")
	mainwin.setTitleAlignment(TITLE_MODE_CENTERED)
	mainwin.addNotice("Welcome to Deadline v0.1")
	mainwin.addNotice("You can type '/quit' to quit," +
		" or type something else to simply see it" +
		" show up in this window :-)")
	gui.show()

	while keep_running:
		try:
			# if ircc.isConnected():
			# 	select.select([sys.stdin, ircs], [], [])
			# else:
			# 	select.select([sys.stdin], [ircs], [])
			# 	ircc.doConnect()
			select.select([sys.stdin], [], [])
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

def quitEvent(str):
	global keep_running
	keep_running = False

def connectEvent(server):
	pass

gui = DeadGUI()
try:
	main()
finally:
	gui.hide()
print "Have a nice day!"

