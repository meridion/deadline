# Deadline the #UvA IRC Bot

import locale
import curses
from curses.wrapper import wrapper as launch_ncurses_app

# Fetch the system locale settings, so ncurses can do its job correctly
# UTF8 strings to be precise
# For more info see: http://docs.python.org/3.1/library/curses.html
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

# Das Entrypoint
def main(stdscr):
	stdscr.clear()
	height, width = stdscr.getmaxyx()
	curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
	infobarcolor = curses.A_DIM | curses.color_pair(1);
	for x in range(width):
		stdscr.addch(0, x, ' ', infobarcolor)
		stdscr.addch(height - 2, x, infobarcolor)

	stdscr.addstr(0, width / 2 - 6, "Deadline v0.1", infobarcolor)
	stdscr.addstr(height - 1, 0, " [Main]")
	stdscr.move(height - 1, 8)
	stdscr.refresh()
	stdscr.getch()

# Autoinitialize ncurses, and make sure we clean up if we crash (or exit)
# This function calls main for us, with the main ncurses window as argument
launch_ncurses_app(main)
print ""

