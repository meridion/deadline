# Deadline ncurses GUI library

import curses, curses.ascii
from time import time, localtime

# The deadline ncurses interface is heavily based on the irssi chat client
class DeadGUI(object):
    def __init__(self):
        self.visible = False
        self.stdscr = None
        self.windows = []
        self.command = {}
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
        curses.use_default_colors()
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
            curses.KEY_DC : self.promptBackspace,
            curses.KEY_LEFT : self.promptLeft,
            curses.KEY_RIGHT : self.promptRight,
            curses.KEY_UP : self.promptUp,
            curses.KEY_DOWN : self.promptDown,
            curses.KEY_ENTER : self.promptExecute,
            curses.KEY_NEXT : self.promptRight,
            curses.KEY_PREVIOUS : self.promptLeft,
            curses.KEY_PPAGE : self.scrollUp,
            curses.KEY_NPAGE : self.scrollDown,
            ord(curses.ascii.ctrl('N')) : self.promptRight,
            ord(curses.ascii.ctrl('P')) : self.promptLeft,

            # Carriage return
            ord('\r') : self.promptExecute
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
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_BLUE, -1)
        curses.init_pair(5, curses.COLOR_RED, -1)
        self.infobarcolor = curses.A_DIM | curses.color_pair(1)
        self.infohookcolor = curses.A_DIM | curses.color_pair(2)
        self.noticecolor = curses.A_DIM | curses.color_pair(3)
        self.incomingcolor = curses.A_DIM | curses.color_pair(4)
        self.outgoingcolor = curses.A_DIM | curses.color_pair(5)
        self.redrawFromScratch()
        self.stdscr.refresh()

    def resizeEvent(self):
        self.stdscr.clear()
        self.height, self.width = self.stdscr.getmaxyx()
        self.promptValidate()
        self.redrawFromScratch()
        self.stdscr.refresh()

    def redrawFromScratch(self):
        self.stdscr.clear()
        w = self.windows[self.current_window]
        w.setArea(0, 0, self.height - 1, self.width)
        w.redrawFromScratch(self)
        self.promptFromScratch()

    def registerCommand(self, cmdname, func):
        self.command[cmdname] = func

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
        if len(self.string):
            if self.string[0] == '/' and len(self.string) > 1:
                s = self.string.find(' ')
                if s < 0:
                    cmd = self.string
                    args = None
                else:
                    cmd = self.string[:s]
                    args = self.string[s + 1:].strip()
                try:
                    self.command[cmd[1:]](args)
                except KeyError:
                    self.getMainWindow(). \
                        addNotice("Unknown command '%s'" % cmd[1:])
            else:
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

    def scrollUp(self):
        amount = max((self.height - 3) / 2, 1)
        self.windows[self.current_window].scrollMessageArea(-amount)
        self.redrawFromScratch()

    def scrollDown(self):
        amount = max((self.height - 3) / 2, 1)
        self.windows[self.current_window].scrollMessageArea(amount)
        self.redrawFromScratch()

TITLE_MODE_CENTERED, TITLE_MODE_LEFT, TITLE_MODE_RIGHT = range(3)

class DeadWindow(object):
    def __init__(self, name = "IHaveNoName"):
        self.messages = []
        self.title = ""
        self.title_mode = TITLE_MODE_LEFT
        self.x, self.y, self.width, self.height = (0,) * 4
        self.name = name
        self.scroll = None
        self.more = False

    def addNotice(self, notice):
        self.addMessage(DeadMessage(DM_NOTICE, notice))

    def addIncoming(self, incoming):
        self.addMessage(DeadMessage(DM_INCOMING, incoming))

    def addOutgoing(self, outgoing):
        self.addMessage(DeadMessage(DM_OUTGOING, outgoing))

    def addMessage(self, message):
        if len(self.messages) == 256:
            self.messages.pop(0)
        self.messages.append(message)
        if self.scroll is not None:
            self.more = True

    def setArea(self, y, x, height, width):
        self.y, self.x = y, x
        self.height, self.width = height, width
        self.scrollMessageArea(0)

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
        if self.scroll is None:
            h = 0
            msg = len(self.messages) 
            while h < self.height - 2:

                msg -= 1
                if msg == -1:
                    msg = 0
                    h = self.height - 2
                    break

                h += self.messages[msg].getRenderSpec(self.width)

            line = h - (self.height - 2)
        else:
            msg, line = self.scroll

        y = self.y + 1
        for message in self.messages[msg:]:
            h = min(message.getRenderSpec(self.width) - line,
                self.height - y - 1)
            message.render(gui, y, self.x, h, self.width, line)
            line = 0
            y += h
            if y >= self.height - 1:
                break

        return True

    def scrollMessageArea(self, amount):
        # Unconditionally fetch message position
        if self.scroll is None:
            if amount >= 0:
                return True

            # Fill the window in 'reverse' to figure out the top message
            # and line
            h = 0
            msg = len(self.messages) - 1 
            while h < self.height - 2:

                # The window is not yet completely filled
                # scrolling is meaningless
                if msg == -1:
                    return True

                h += self.messages[msg].getRenderSpec(self.width)
                msg -= 1

            line = h - (self.height - 2)
        else:
            msg, line = self.scroll

        # This is necessary since the width of the window might've been
        # changed since last time this function was called
        h = self.messages[msg].getRenderSpec(self.width)
        line = min(line, h)

        # Scroll down
        if amount > 0:
            # Allign to message border
            amount -= h - line
            msg += 1
            line = 0
            while amount > 0 and msg < len(self.messages):
                amount -= self.messages[msg].getRenderSpec(self.width)
                msg += 1

        # Scroll up
        if amount < 0:
            # Allign to message border
            amount += line
            line = 0
            while amount < 0 and msg > 0:
                msg -= 1
                amount += self.messages[msg].getRenderSpec(self.width)

        # Hit the top
        if amount < 0:
            self.scroll = (0, 0)
            return True

        # Hit the bottom
        if msg == len(self.messages):
            self.scroll = None
            return True

        # Scroll within current top message
        self.scroll = (msg, amount)

        # Fill window and test for incomplete fills
        h = self.messages[msg].getRenderSpec(self.width) - amount
        msg += 1
        while msg < len(self.messages):
            h += self.messages[msg].getRenderSpec(self.width)
            msg += 1
        if h <= self.height - 2:
            self.scroll = None

        return True

    def drawInfo(self, gui):
        if self.scroll is None:
            self.more = False

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

        if self.more:
            gui.stdscr.addstr(self.y + self.height - 1, self.width - 11,
                '-- more --', gui.infobarcolor)

DM_RAW, DM_NOTICE, DM_CHAT, DM_INCOMING, DM_OUTGOING = range(5)

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
            Compute how many lines of text this message will take
            for the given width.
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
            Render a message object to the GUI.
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
            elif self.type == DM_INCOMING:
                gui.stdscr.addstr(y, x + 6, '>> ', gui.incomingcolor)
            elif self.type == DM_OUTGOING:
                gui.stdscr.addstr(y, x + 6, '<< ', gui.outgoingcolor)
            else:
                gui.stdscr.addstr(y, x + 6, '** ')
            gui.stdscr.addstr(y, x + self.prefix_length, broken)
            y += 1
        lines = 1
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

