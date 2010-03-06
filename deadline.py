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
import socket

# Global settings variables
keep_running = True
gui_running = False

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
locale.setlocale(locale.LC_ALL, '')

# Das Entrypoint
def main():
	mainwin = gui.getMainWindow()
	mainwin.setTitle("Deadline v0.1")
	mainwin.setTitleAlignment(TITLE_MODE_CENTERED)
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
		self.main_window = self.createWindow("Main")
		self.current_window = 0

	def show(self):
		"""
Show the deadline ncurses GUI.
		"""
		if self.visible:
			return False
		self.stdscr = curses.initscr()
		curses.start_color()
		curses.noecho()
		curses.cbreak()
		curses.nonl()
		self.stdscr.keypad(1)
		self.visible = True
		self.__ncurses_init__()
		return True

	def hide(self):
		"""
Go back to the normal terminal.
		"""
		if not self.visible:
			return False
		self.stdscr.keypad(0)
		curses.nocbreak()
		curses.echo()
		curses.endwin()
		del self.stdscr
		self.visible = False
		return True

	def getMainWindow(self):
		return self.main_window

	def createWindow(self, name):
		win = DeadWindow(name)
		self.windows.append(win)
		return win

	def __ncurses_init__(self):
		# Setup input handler
		self.stdscr.nodelay(1)
		self.special = {
			curses.KEY_RESIZE : self.resizeEvent,
			curses.KEY_BACKSPACE : self.promptBackspace,
			curses.ascii.DEL : self.promptBackspace,
			curses.KEY_LEFT : self.promptLeft,
			curses.KEY_RIGHT : self.promptRight,
			curses.KEY_ENTER : self.promptExecute,

			# Carriage return
			13 : self.promptExecute
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
		curses.init_pair(2, curses.COLOR_MAGENTA, curses.COLOR_RED)
		curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
		self.infobarcolor = curses.A_DIM | curses.color_pair(1)
		self.infohookcolor = curses.A_DIM | curses.color_pair(2)
		self.noticecolor = curses.A_DIM | curses.color_pair(3)
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
		self.stdscr.refresh()
		return True

	# Prompt functionality
	def promptFromScratch(self):
		"""
Redraws the prompt from scratch.
		"""
		# Draw prompt message
		self.stdscr.addstr(self.height - 1, 0, self.prompt)
		self.stdscr.addstr(self.height - 1, len(self.prompt) + 1,
			self.string[self.view:self.view + self.width -
			len(self.prompt) - 2])

		# Fill with spaces if nothing is here
		if self.position == len(self.string):
			spacepos = len(self.prompt) + 1 + self.position - self.view
			self.stdscr.addstr(self.height - 1, spacepos, ' ' *
				(self.width - 1 - spacepos))

		# Place cursor
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

	def promptExecute(self):
		"""
Executes the command typed into the prompt.
		"""
		global keep_running

		if self.string == "/quit":
			keep_running = False
		self.getMainWindow().addNotice(self.string)
		self.promptClear()
		self.redrawFromScratch()

	def promptClear(self):
		"""
Clear the contents of the prompt.
		"""
		self.string = ""
		self.position = 0
		self.view = 0

TITLE_MODE_CENTERED, TITLE_MODE_LEFT, TITLE_MODE_RIGHT = range(3)

class DeadWindow(object):
	def __init__(self, name = "IHaveNoName"):
		self.messages = []
		self.title = ""
		self.title_mode = TITLE_MODE_LEFT
		self.x, self.y, self.width, self.height = 0, 0, 0, 0
		self.name = name

	def addNotice(self, notice):
		self.messages.append(DeadMessage(DM_NOTICE, notice))

	def setArea(self, y, x, height, width):
		self.y, self.x = y, x
		self.height, self.width = height, width

	def setTitle(self, title):
		self.title = title

	def setTitleAlignment(self, alignment):
		self.title_mode = alignment

	def redrawFromScratch(self, gui):
		self.drawTitle(gui)
		self.drawMessageArea(gui)
		self.drawInfo(gui)

	def drawTitle(self, gui):
		# Title bar
		if self.title_mode == TITLE_MODE_LEFT:
			str = self.title + (self.width - len(self.title)) * ' '
		elif self.title_mode == TITLE_MODE_RIGHT:
			str = (self.width - len(self.title)) * ' ' + self.title
		else:
			pos = self.width / 2 - len(self.title) / 2
			str = ' ' * pos + self.title + ' ' * \
				(self.width - pos - len(self.title))
		gui.stdscr.addstr(self.y, self.x, str, gui.infobarcolor)

	def drawMessageArea(self, gui):
		y = self.y + 1
		for message in self.messages:
			h = message.getRenderSpec(self.width)
			message.render(gui, y, self.x, h, self.width, 0)
			y += h

	def drawInfo(self, gui):
		# Infobar
		gui.stdscr.addch(self.y + self.height - 1, self.x,
			' ', gui.infobarcolor)

		# Clock
		clock = localtime()
		clockstr = "%(hour)02d:%(min)02d" % \
			{"hour" : clock.tm_hour, "min" : clock.tm_min}
		gui.stdscr.addch(self.y + self.height - 1, self.x + 1,
			'[', gui.infohookcolor)
		gui.stdscr.addstr(self.y + self.height - 1, self.x + 2,
			clockstr, gui.infobarcolor)
		gui.stdscr.addch(self.y + self.height - 1, self.x + 7,
			']', gui.infohookcolor)

		# Infobar
		gui.stdscr.addstr(self.y + self.height - 1, self.x + 8,
			' ' * (self.width - 8), gui.infobarcolor)

DM_RAW, DM_NOTICE, DM_CHAT = range(3)

class DeadMessage(object):
	def __init__(self, type = DM_RAW, content = "You're code is bugged ;-)"):
		self.timestamp = time()
		self.type = type
		self.content = content
		self.prefix_length = 9

	def breakString(self, text, width):
		"""
Function helper for building text wrappers.

'text' should contain a string to be wrapped, and
'width' should be the target width the textbox will be.

The function shall return a tuple containing the string
to be displayed and the remainder.
		"""

		if width > len(text):
			return text, ""

		# Find last space
		i = width - 1
		while i >= 0 and text[i] != ' ':
			i -= 1
		if i == -1:
			return text[:width], text[width:].lstrip()
		rest = text[i + 1:]
		breakpoint = i

		# Throw away trailing spaces
		i -= 1
		while i >= 0 and text[i] == ' ':
			i -= 1
		if i == -1:
			broken = text[:breakpoint]
		else:
			broken = text[:i + 1]
		return broken, rest.lstrip()

	def getRenderSpec(self, width):
		"""
Compute how many lines of text this message will take for the given width
		"""
		lines = 1
		prebreak = self.content
		broken, rest = self.breakString(prebreak,
			width - self.prefix_length)
		while len(rest):
			lines += 1
			if len(broken) + len(rest) == len(prebreak):
				prebreak = rest
				broken, rest = self.breakString(prebreak, width)
			else:
				prebreak = rest
				broken, rest = self.breakString(
					prebreak, width - self.prefix_length)
		return lines

	def render(self, gui, y, x, height, width, startline):
		"""
Render a message object to the GUI
		"""
		prebreak = self.content
		broken, rest = self.breakString(prebreak,
			width - self.prefix_length)
		if startline == 0:
			clock = localtime(self.timestamp)
			clockstr = "%(hour)02d:%(min)02d" % \
				{"hour" : clock.tm_hour, "min" : clock.tm_min}
			gui.stdscr.addstr(y, x, clockstr)
			if self.type == DM_NOTICE:
				gui.stdscr.addstr(y, x + 6, '-- ', gui.noticecolor)
			else:
				gui.stdscr.addstr(y, x + 6, '** ')
			gui.stdscr.addstr(y, x + self.prefix_length, broken)
		lines = 1
		y += 1
		while len(rest):
			if len(broken) + len(rest) == len(prebreak):
				prebreak = rest
				broken, rest = self.breakString(prebreak, width)
				if lines >= startline and lines < startline + height:
					gui.stdscr.addstr(y, x, broken)
					y += 1
			else:
				prebreak = rest
				broken, rest = self.breakString(
					prebreak, width - self.prefix_length)
				if lines >= startline and lines < startline + height:
					gui.stdscr.addstr(y, x + self.prefix_length, broken)
					y += 1
			lines += 1
		return True

class DeadEvent(object):
	def __init__(self, delay):
		self.delay = delay
		self.eid = -1

	def trigger(self):
		"""
Method called when event occurs.
		"""
		pass

	def getDelay(self):
		return self.delay

	def setEID(self, eid):
		self.eid = eid

	def getEID(self):
		return self.eid

	def elapseTime(self, time):
		"""
Elapse 'time' units of time.
If the event is triggered the function returns True
		"""
		self.delay -= time
		if self.delay <= 0.0:
			self.trigger()
			return True
		return False

class DeadEventQueue(object):
	def __init__(self):
		self.events = []
		self.eids = 0
		self.elapsing = False

	def scheduleEvent(self, event):
		"""
Schedule an event for execution.

The function shall return the event-code that can be used to cancel the event.
		"""

		eid = self.generateEID()
		event.setEID(eid)

		# Since it is possible for events to be scheduled
		# during the execution of elapseTime (which would ruin our queue)
		# (Events can re-schedule themselves upon triggering)
		# we defer those calls until the elapse call is complete
		if self.elapsing:
			self.schedules.append(event)
			return eid

		self._insertEvent(event)
		return eid

	def cancelEvent(self, eid):
		"""
Cancel an event as specified by it's EID
		"""

		# Same goes for events being cancelled
		if self.elapsing:
			self.cancels.append(eid)
		else:
			self.events = filter(lambda e: e.getEID() != eid, self.events)

	def elapseTime(self, time):
		"""
"Atomically" elapse the time of events in the queue
		"""
		self.scheds = []
		self.cancels = []

		# Do elapse
		self.elapsing = True
		self.events = filter(lambda e: not e.elapseTime(time), self.events)
		self.elapsing = False

		# Insert events scheduled in the mean time
		for e in scheds:
			self._insertEvent(e)

		for eid in cancels:
			self.cancelEvent(eid)

		del self.cancels
		del self.scheds

	def _insertEvent(self, e):
		"""
Internal function that inserts an event in the queue at the right place

e: Event to be insterted

This function returns nothing.
		"""
		d = e.getDelay()
		for i in range(len(self.events)):
			if d < self.events[i].getDelay():
				self.insert(i, e)
				return
		self.append(e)

	def _generateEID(self):
		"""
Internal function for generating EIDs.
		"""

		# To try and keep the EIDs low we use an algorithm
		# that allocates EID spaces of size 1024 and tries
		# to clame the lowest space available

		# Check if we have no more EIDs left
		if self.neid == self.eid_roof:
			eids = map(lambda e: e.getEID(), self.events)
			eids.sort()

			# Search for a 1024 EID gap
			eids.insert(0, -1)
			for i in range(len(eids) - 1):
				if eids[i + 1] - eids[i] >= 1024:
					self.neid = eids[i] + 1
					self.eid_roof = eids[i + 1]
					return self._generateEID()

			# If we were unable to find one create a new one at the end
			self.neid = eids[len(eids) - 1] + 1
			self.eid_roof = self.neid + 1024
			return self._generateEID()
		else:
			eid = self.neid
			self.neid += 1
			return eid

gui = DeadGUI()
try:
	main()
finally:
	gui.hide()
print "Have a nice day!"

