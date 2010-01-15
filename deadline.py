# Deadline the #UvA IRC Bot

import os

# Verify we are not on Windows (NTKRN)
if os.name == 'nt':
	print """Sorry, Deadline is not supported on Windows
due to their implementation of the POSIX select() function"""
	exit(1)

# Import all required stuff
import sys
from errno import EINTR
import locale
import curses, curses.ascii
from curses.wrapper import wrapper as launch_ncurses_app
import select

# Global settings variables
keep_running = True

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

# Das Entrypoint
def main(stdscr):
	stdscr.nodelay(1)
	gui = DeadGUI(stdscr)
	while keep_running:
		try:
			select.select([sys.stdin], [], [])
		except select.error, e:
			if e.args[0] == EINTR:
				# We might've been interrupted by a SIGWINCH
				# signal, which means we need to resize our
				# window
				while gui.inputEvent():
					pass
				continue
			else:
				raise e
		while gui.inputEvent():
			pass

# The deadline ncurses interface is heavily based on the irssi chat client
class DeadGUI(object):
	def __init__(this, stdscr):
		# Setup input handler
		this.special = {
			curses.KEY_RESIZE : this.resizeEvent,
			curses.KEY_BACKSPACE : this.promptBackspace,
			curses.ascii.DEL : this.promptBackspace,
			curses.KEY_LEFT : this.promptLeft,
			curses.KEY_RIGHT : this.promptRight,
		}

		# Setup prompt
		this.prompt = "[Main]"
		this.string = ""
		this.position = 0
		this.view = 0

		# Initialize the display
		this.stdscr = stdscr
		this.stdscr.clear()
		this.height, this.width = stdscr.getmaxyx()
		curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
		this.infobarcolor = curses.A_DIM | curses.color_pair(1);
		this.redrawFromScratch()
		this.stdscr.refresh()

	def resizeEvent(this):
		this.stdscr.clear()
		this.height, this.width = this.stdscr.getmaxyx()
		this.promptValidate()
		this.redrawFromScratch()
		this.stdscr.refresh()

	def redrawFromScratch(this):
		for x in range(this.width):
			this.stdscr.addch(0, x, ' ', this.infobarcolor)
			this.stdscr.addch(this.height - 2, x, ' ', this.infobarcolor)

		this.stdscr.addstr(0, this.width / 2 - 7, "Deadline v0.1",
			this.infobarcolor)
		this.promptFromScratch()

	def inputEvent(this):
		c = this.stdscr.getch()
		if c == -1:
			return False
		try:
			this.special[c]()
		except KeyError:
			this.promptInput(chr(c))
		return True

	# Prompt functionality
	def promptFromScratch(this):
		this.stdscr.addstr(this.height - 1, 0, this.prompt)
		this.stdscr.addstr(this.height - 1, len(this.prompt) + 1,
			this.string[this.view:this.view + this.width -
			len(this.prompt) - 2])

		# Fill with spaces if nothing is here
		if this.position == len(this.string):
			spacepos = len(this.prompt) + 1 + this.position - this.view
			this.stdscr.addstr(this.height - 1, spacepos, ' ' * (this.width - 1 -
				spacepos))
		this.stdscr.move(this.height - 1, len(this.prompt) + 1 + this.position -
			this.view)

	def promptInput(this, x):
		this.string = this.string[:this.position] + x + \
			this.string[this.position:]
		this.position += 1;
		if this.promptValidate():
			this.promptFromScratch()
		else:
			# Put the character before the cursor, and the cursor in the new
			# current position.
			this.stdscr.insch(this.height - 1, len(this.prompt) +
				this.position - this.view, x)
			this.stdscr.move(this.height - 1, len(this.prompt) + 1 +
				this.position - this.view)

	def promptBackspace(this):
		if this.position != 0:
			this.string = this.string[:this.position - 1] + \
				this.string[this.position:]
			this.position -= 1
			if this.promptValidate():
				this.promptFromScratch()
			else:
				this.stdscr.delch(this.height - 1, len(this.prompt) +
					1 + this.position - this.view)
				this.stdscr.move(this.height - 1, len(this.prompt) +
					1 + this.position - this.view)

	def promptLeft(this):
		if this.position != 0:
			this.position -= 1
			if this.promptValidate():
				this.promptFromScratch()
			else:
				this.stdscr.move(this.height - 1, len(this.prompt) + 1 +
					this.position - this.view)

	def promptRight(this):
		if this.position != len(this.string):
			this.position += 1
			if this.promptValidate():
				this.promptFromScratch()
			else:
				this.stdscr.move(this.height - 1, len(this.prompt) + 1 +
					this.position - this.view)

	# Verify that the prompt is in a displayable state
	# If it is not, fix it and return True, otherwise return False
	def promptValidate(this):
		# If we scroll too much to left (or backspace)
		# We need the terminal to scroll the text
		# View defines how much our text is scrolled
		if this.position - this.view < 0:
			this.view = this.view - this.width / 4
			if this.view < 0:
				this.view = 0
			return True

		# Same but now for to the right
		if this.position - this.view > this.width - 2 - len(this.prompt):
			this.view = this.view + this.width / 4
			if this.view > this.position:
				this.view = this.position
			return True
		return False

# Autoinitialize ncurses, and make sure we clean up if we crash (or exit)
# This function calls main for us, with the main ncurses window as argument
launch_ncurses_app(main)
print ""

