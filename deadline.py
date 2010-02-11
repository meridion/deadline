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
from time import time, localtime
import select

# Global settings variables
keep_running = True
gui_running = False

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

# Das Entrypoint
def main():
	gui.show()
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
	def __init__(self):
		self.visible = False
		self.stdscr = None
		self.windows = []
		self.main = self.createWindow("Main")
		self.current_window = 0

	def show(self):
		if self.visible:
			return False
		self.stdscr = curses.initscr()
		curses.start_color()
		curses.noecho()
		curses.cbreak()
		self.stdscr.keypad(1)
		self.visible = True
		self.__ncurses_init__()
		return True

	def hide(self):
		self.stdscr.keypad(0)
		curses.nocbreak()
		curses.echo()
		curses.endwin()
		del self.stdscr
		self.visible = False

	def getMainWindow(self):
		return self.main

	def createWindow(self, name):
		win = DeadWindow(name)
		self.windows.append(win)

	def __ncurses_init__(self):
		# Setup input handler
		self.stdscr.nodelay(1)
		self.special = {
			curses.KEY_RESIZE : self.resizeEvent,
			curses.KEY_BACKSPACE : self.promptBackspace,
			curses.ascii.DEL : self.promptBackspace,
			curses.KEY_LEFT : self.promptLeft,
			curses.KEY_RIGHT : self.promptRight,
		}

		# Setup prompt
		self.prompt = "[Main]"
		self.string = ""
		self.position = 0
		self.view = 0

		# Initialize the display
		self.stdscr.clear()
		self.height, self.width = self.stdscr.getmaxyx()
		curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
		self.infobarcolor = curses.A_DIM | curses.color_pair(1);
		self.redrawFromScratch()
		self.stdscr.refresh()

	def resizeEvent(self):
		self.stdscr.clear()
		self.height, self.width = self.stdscr.getmaxyx()
		self.promptValidate()
		self.redrawFromScratch()
		self.stdscr.refresh()

	def redrawFromScratch(self):
		w = self.windows[self.current_window]
		w.setArea(0, 0, self.height - 1, self.width)
		w.redrawFromScratch(self)
		self.promptFromScratch()

	def inputEvent(self):
		c = self.stdscr.getch()
		if c == -1:
			return False
		try:
			self.special[c]()
		except KeyError:
			self.promptInput(chr(c))
		return True

	# Prompt functionality
	def promptFromScratch(self):
		self.stdscr.addstr(self.height - 1, 0, self.prompt)
		self.stdscr.addstr(self.height - 1, len(self.prompt) + 1,
			self.string[self.view:self.view + self.width -
			len(self.prompt) - 2])

		# Fill with spaces if nothing is here
		if self.position == len(self.string):
			spacepos = len(self.prompt) + 1 + self.position - self.view
			self.stdscr.addstr(self.height - 1, spacepos, ' ' * (self.width - 1 -
				spacepos))
		self.stdscr.move(self.height - 1, len(self.prompt) + 1 + self.position -
			self.view)

	def promptInput(self, x):
		self.string = self.string[:self.position] + x + \
			self.string[self.position:]
		self.position += 1;
		if self.promptValidate():
			self.promptFromScratch()
		else:
			# Put the character before the cursor, and the cursor in the new
			# current position.
			self.stdscr.insch(self.height - 1, len(self.prompt) +
				self.position - self.view, x)
			self.stdscr.move(self.height - 1, len(self.prompt) + 1 +
				self.position - self.view)

	def promptBackspace(self):
		if self.position != 0:
			self.string = self.string[:self.position - 1] + \
				self.string[self.position:]
			self.position -= 1
			if self.promptValidate():
				self.promptFromScratch()
			else:
				self.stdscr.delch(self.height - 1, len(self.prompt) +
					1 + self.position - self.view)
				self.stdscr.move(self.height - 1, len(self.prompt) +
					1 + self.position - self.view)

	def promptLeft(self):
		if self.position != 0:
			self.position -= 1
			if self.promptValidate():
				self.promptFromScratch()
			else:
				self.stdscr.move(self.height - 1, len(self.prompt) + 1 +
					self.position - self.view)

	def promptRight(self):
		if self.position != len(self.string):
			self.position += 1
			if self.promptValidate():
				self.promptFromScratch()
			else:
				self.stdscr.move(self.height - 1, len(self.prompt) + 1 +
					self.position - self.view)

	# Verify that the prompt is in a displayable state
	# If it is not, fix it and return True, otherwise return False
	def promptValidate(self):
		# If we scroll too much to left (or backspace)
		# We need the terminal to scroll the text
		# View defines how much our text is scrolled
		if self.position - self.view < 0:
			self.view = self.view - self.width / 4
			if self.view < 0:
				self.view = 0
			return True

		# Same but now for to the right
		if self.position - self.view > self.width - 2 - len(self.prompt):
			self.view = self.view + self.width / 4
			if self.view > self.position:
				self.view = self.position
			return True
		return False

TITLE_MODE_CENTERED, TITLE_MODE_LEFT, TITLE_MODE_RIGHT = range(3)

class DeadWindow(object):
	def __init__(self, name = "IHaveNoName"):
		self.messages = []
		self.title = ""
		self.title_mode = TITLE_MODE_RIGHT
		self.x, self.y, self.width, self.height = 0, 0, 0, 0
		self.name = name

	def addNotice(self, notice):
		self.messages.append(DeadMessage(DM_NOTICE, notice))

	def setArea(self, y, x, height, width):
		self.y, self.x = y, x
		self.height, self.width = height, width

	def redrawFromScratch(self, gui):
		self.drawTitle(gui)
		self.drawMessageArea(gui)
		self.drawInfo(gui)

	def drawTitle(self, gui):
		# Title bar
		if self.title_mode == TITLE_MODE_LEFT:
			str = self.title + (width - len(self.title)) * ' '
		elif self.title_mode == TITLE_MODE_RIGHT:
			str = (self.width - len(self.title)) * ' ' + self.title
		else:
			pos = width / 2 - len(self.title) / 2
			str = ' ' * pos + self.title + ' ' * \
				(width - pos - len(self.title))
		gui.stdscr.addstr(self.y, self.x, str, gui.infobarcolor)

	def drawMessageArea(self, gui):
		pass

	def drawInfo(self, gui):
		# Infobar
		gui.stdscr.addstr(self.y + self.height - 1, self.x,
			' ' * self.width, gui.infobarcolor)

DM_RAW, DM_NOTICE, DM_CHAT = range(3)

class DeadMessage(object):
	def __init__(self, type = DM_RAW, content = "You're code is bugged ;-)"):
		self.timestamp = time()
		self.type = type
		self.content = content

gui = DeadGUI()
try:
	main()
finally:
	gui.hide()
print "Have a nice day!"

