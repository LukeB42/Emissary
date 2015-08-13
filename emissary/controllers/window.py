#! _*_ coding: utf-8 _*_
# Defines a simple ncurses window, an event loop and some panes.
# Luke Brooks, sponsored by Redflag A!ert. 2015.
import time
import _curses
VERSION = "0.0.1"

FIT     = "FIT"    # pane axis hugs its content
EXPAND  = "EXPAND" # stretch on axis as much as possible
# These values let us align pane content
ALIGN_LEFT  = "ALIGN_LEFT" 
ALIGN_RIGHT = "ALIGN_RIGHT" 
ALIGN_CENTER= "ALIGN_CENTER"

class WindowError(Exception):
	def __init__(self, message):
		self.message = message

	def __str__(self):
		return(repr(self.message))

class PaneError(Exception):
	def __init__(self, message):
		self.message = message

	def __str__(self):
		return(repr(self.message))

class Window(object):
	"""
	A window can have multiple panes responsible for different things.
	This object filters input characters through the .process_input() method on all
	panes marked as active.
	
	The list of panes orders panes vertically from highest to lowest.
	Elements in the list of panes can also be lists of panes ordered from left to right.

	Set blocking to True to wait for input before redrawing the screen.
	Set debug to True to draw any exception messages and to print character codes on the last line.
	"""
	running    = None
	blocking   = None
	debug      = None
	window     = None
	height     = None
	width      = None
	panes      = []
	pane_cache = []
	exit_keys  = []
	friendly   = True

	def __init__(self, blocking=False):
		"""
		Create a Window instance.

		You may want to wait for user input if the connection is over SSH.
		This can be done by checking for 'SSH_CONNECTION' in os.environ.
		"""
		self.blocking = blocking

	def start(self):
		"""
		Window event loop
		"""
		self.window = _curses.initscr()
		_curses.savetty()
		_curses.start_color()
		_curses.use_default_colors()
		self.window.leaveok(1)
		_curses.raw()
		self.window.keypad(1)
		_curses.start_color()
		_curses.use_default_colors()
		_curses.noecho()
		_curses.cbreak()
		_curses.nonl()
		if self.blocking:
			self.window.nodelay(0)
		else:
			self.window.nodelay(1)
		self.running = True
		while self.running:
			self.draw()
			self.process_input()
			if self.friendly:
				time.sleep(0.030)
		self.stop()

	def stop(self):
		"""
		Restore the TTY to its original state.
		"""
		_curses.nocbreak()
		self.window.keypad(0)
		_curses.echo()
		_curses.resetty()
		_curses.endwin()
		self.running = False

	def draw(self):
		# Check for a resize
		self.update_window_size()

		# Compute the coordinates of all currently attached panes
		self.calculate_pane_heights_and_widths()
		self.coordinate()

		# update all pane content
		[pane.update() for pane in self if not pane.hidden]

		# Draw panes within their areas based on pane.coords
		# Draw pane frames, accounting for alignment, to window coordinates.
		# If, for example, a pane is self-coordinating and its bottom right value
		# is higher than its top right, then we can deduce that the square left with
		# top-right as its lower-left is to be omitted from being drawn with this pane.
		# Coordinates are of the form:
		# [
		#   ((top-left-from-top, top-left-from-left),
		#    (top-right-from-top, top-right-from-left)),
		#   ((bottom-left-from-top, bottom-left-from-left),
		#    (bottom-right-from-top, bottom-right-from-left))
		# ]

		for pane in self:
			if pane.hidden: continue
			# Set y,x to top left of pane.coords
			top_left_top       = pane.coords[0][0][0]
			top_left_left      = pane.coords[0][0][1]
			top_right_top      = pane.coords[0][1][0]
			top_right_left     = pane.coords[0][1][1]
			bottom_left_top    = pane.coords[1][0][0]
			bottom_left_left   = pane.coords[1][0][1]
			bottom_right_top   = pane.coords[1][1][0]
			bottom_right_left  = pane.coords[1][1][1]

			y = 0 # from top
			x = 0 # from left
			for frame in pane.content:
				(text, align, attrs) = frame
				for i, line in enumerate(text.split("\n")):

					# Don't attempt to draw below the window
					if i+y > pane.height: break
#					if i+y > bottom_left_top or i+y > bottom_right_top: break

					l = len(line)
					# Truncate non-wrapping panes
					if not pane.wrap:
#						self.truncate_to_fit(line, pane.coords)
						# Honour inverted upper right corners
						if top_right_top > top_left_top or top_right_left < bottom_right_left:
							# if the current cursor is above or level with
							# where the top-right corner inverts
							if y >= top_right_top:
								# and the bottom left inverts
								if bottom_left_top < bottom_right_top and y >= bottom_left_top:
									# then perform lower left to top right corner inversion
									line = line[:top_right_left - bottom_left_left]
								else:
									# otherwise our line length is from the top left to the top-right
									line = line[:top_right_left - top_left_left]

						# Honour inverted lower right corners
						if bottom_right_top < bottom_left_top or top_right_left > bottom_right_left:
							# if the current cursor is below or level with
							# where the lower-right corner inverts
							if y >= bottom_right_top:
								# and the top left inverts
								if top_left_top > top_right_top and y >= top_left_top:
									# then perform upper left to lower right inversion
									line = line[:bottom_right_left - top_left_left]
								# otherwise our line length is from bottom left to bottom right
								else:
									line = line[:bottom_right_left - bottom_left_left]

						# Honour inverted upper left corners
						if top_left_left > bottom_left_left or top_left_top > top_right_top:
							# if the current cursor is above or level with
							# where the top-left corner inverts
							if y >= top_left_top:
								# and the lower right inverts
								if bottom_right_top < bottom_left_top and y >= bottom_right_top:
									# perform upper left to lower right inversion
									line = line[:bottom_right_left - top_left_left]
								# otherwise we're just fitting to the coordinates
								else:
									line = line[:top_right_left - top_left_left]

						# Honour inverted lower left corners
						if bottom_left_left > top_left_left:
							# if the current cursor is below or level with
							# where the lower left corner inverts
							if y >= bottom_left_top:
								# and the upper right inverts
								if top_right_top > top_left_top and y <= top_right_top:
									# perform lower left to top right inversion
									line = line[:top_right_left - bottom_left_left]
								# otherwise we're just fitting to the coordinates
								else:
									line = line[:bottom_right_left - bottom_left_left]

						# All non-wrapping panes
						if l > pane.width:
							line = line[:pane.width]
						if top_left_left+x+l > self.width:
							line = line[:self.width - top_left_left]

					# Purposefully wrap panes by incrementing y and resetting x
					# pane.wrap = 1 for wordwrapping
					# pane.wrap = 2 for character wrapping
					else:
						# The important thing to remember is that the "first line"
						# of a wrapping line is coming through this path

						# TODO: Wrap text based on the coordinate system
						if top_left_left+x+l > top_right_left - top_left_left:
							hilight_attrs = attrs

							if self.debug:
								hilight_attrs = palette("black", "yellow")
							else:
								hilight_attrs = attrs

							if pane.wrap == 1 or pane.wrap == True:
								line = line.split()
								l = len(line)
							for c,j in enumerate(line):
								if y > bottom_left_top - top_left_top: break
								# Place a space between words after the first if word-wrapping
								if c and isinstance(line, list):
									j = ' ' + j
								# Move to the next line if the cursor + j would draw past the top right
								if top_left_left+x+len(j) > top_right_left:
									y += 1
									x  = 0
									# Draw ... if j doesnt fit in the line
									if len(j) > top_right_left - top_left_left+x:
										t = '...'[:(top_right_left - top_left_left+x)]
										self.addstr(top_left_top+i+y, top_left_left+x, t, hilight_attrs)
										y += 1
										x = 0
										continue
								self.addstr(top_left_top+i+y, top_left_left+x, j, hilight_attrs)
								x += len(j)

							# Process next line in current frame
							# the value for i will increment
							if self.debug:
								self.addstr(self.height-8,0, str(i))
								self.addstr(self.height-7,0, str(c))
								self.addstr(self.height-6,0, str(x))
							x = 0
							continue
					# TODO: Text alignment

					# Account for an inverted top left corner
					if top_left_top > top_right_top and y >= top_left_top:
						self.addstr(top_left_top+i+y, bottom_left_left+x, line, attrs)
					# Account for an inverted bottom left corner
					elif bottom_left_top < bottom_right_top and y >= bottom_left_top:
						self.addstr(top_left_top+i+y, bottom_left_left+x, line, attrs)
					else:
						self.addstr(top_left_top+i+y, top_left_left+x, line, attrs)
					x=0
				# leave cursor at the end of the last line after processing the frame.
				x = l
				y += i

	def process_input(self):
		# Get input
		try:
			character = self.window.getch()
		except Exception, e:
			character = -1
			if self.debug:
				self.addstr(self.height-1, self.width - len(e.message) + 1, e.message)

		# Check for any keys we've been told to exit on
		if character in self.exit_keys:
			self.stop()

		# Force redraw the screen on ^L
		if character == 12:
			self.window.clear()
			return

		# Send input to active panes (hidden panes can still receive input)
		if character != -1:
			[pane.process_input(character) for pane in self if pane.active ]

			# Print character codes to the bottom center if debugging.
			if self.debug:
				self.addstr(self.height-1, self.width/2, " "*4)
				self.addstr(self.height-1, self.width/2 - len(str(character)) / 2, str(character))

	def calculate_pane_heights_and_widths(self):
		"""
		Update pane heights and widths based on the current window and their desired geometry.

		What to bear in mind:
		  Panes may have a fixed desired size.
		  Panes may be set to expand maximally on either axis.
		  Panes may be set to fit to the sum of their content buffers (accounting for alignment).
		  Panes may be set to float.
		  Two panes set to float and expand on the same axis will not overlap.
		  EXPANDing panes may be adjacent to non-floating self-coordinating panes...

		Two panes wanting a height of ten each on a five line window will overflow offscreen.
		Using FIT for an axis on an undersized Window will also overflow offscreen.

		"""
		# Do a pass for heights
		# Every pane must be represented in order to map properly later
		growing_panes      = []
		claimed_columns    = 0
		for v_index, element in enumerate(self.panes):
			# Get maximal height from panes in sublists
			if type(element) == list:
				expanding_in_sublist = [] # A list we'll append to growing_panes
				claimed_from_sublist = [] # The heights gleaned from this pass
				for h_index, pane in enumerate(element):
					if pane.hidden: continue

					# Let height be max L/R distance from top if self-coordinating
					if pane.coords and pane.self_coordinating:
						pane.height = max([pane.coords[1][0][0],pane.coords[1][1][0]])
						claimed_from_sublist.append(pane.height)
						continue

					if len(pane.geometry) < 2:
						pane.height = 0
						continue

					desired_height = pane.geometry[1]

					if isinstance(desired_height, int):
						pane.height = desired_height
						claimed_from_sublist.append(pane.height)
						continue

					elif isinstance(desired_height, str):
						# Calculate the width of panes set to FIT
						if desired_height == FIT:
							buffer = ""
							for frame in pane.content:
								buffer += frame[0]
							pane.height = len(buffer.split('\n'))
							claimed_from_sublist.append(pane.height)
							continue

						elif desired_height == EXPAND:
							expanding_in_sublist.append(pane)
							continue

					pane.height = desired_height

				# Append any expanding panes to growing_panes as a list
				if expanding_in_sublist:
					growing_panes.append(expanding_in_sublist)

				# The total claimed columns for this sublist:
				if claimed_from_sublist:
					claimed_columns += max(claimed_from_sublist)
			else:
				if element.hidden: continue

				if element.coords and element.self_coordinating:
					element.height = max([element.coords[1][0][0], element.coords[1][1][0]])
					claimed_columns += element.height
					continue

				if len(element.geometry) < 2:
					element.height = 0
					continue

				desired_height = element.geometry[1]

				if isinstance(desired_height, int):
					element.height = desired_height
					claimed_columns += element.height
					continue

				elif isinstance(desired_height, str):
					# Calculate the width of panes set to FIT
					if desired_height == FIT:
						buffer = ""
						for frame in element.content:
							buffer += frame[0]
						element.height = len(buffer.split('\n'))
						claimed_columns += element.height
						continue

					elif desired_height == EXPAND:
						growing_panes.append(element)
						continue

				element.height = desired_height

		# Calculate how many columns are left by panes with fixed heights
		if growing_panes:
			remaining_space = self.height - claimed_columns
			typical_expanse = remaining_space / len(growing_panes)
			for pane in growing_panes:
				if isinstance(pane, list):
					for p in pane:
						p.height = typical_expanse
				else:
					pane.height = typical_expanse

		# Then a pass for widths.
		for v_index, element in enumerate(self.panes):
			claimed_rows    = 0
			growing_panes   = []
			# Get panes who will be sharing the x axis
			if type(element) == list:
				for h_index, pane in enumerate(element):
					if pane.hidden: continue

					# Calculate the widest part of a self-coordinating pane
					if pane.coords and pane.self_coordinating:
						rightmost = [pane.coords[0][1][1],pane.coords[1][1][1]]
						pane.width = max(rightmost)
						continue

					if not pane.geometry:
						pane.width = 0
						continue

					desired_width = pane.geometry[0]

					if isinstance(desired_width, int):
						claimed_rows += desired_width
						pane.width = desired_width
						continue

					elif isinstance(desired_width, str):
						# Calculate the width of panes set to FIT
						if desired_width == FIT:
							buffer = ""
							for frame in pane.content:
								buffer += frame[0]
							pane.width = max(map(len, buffer.split('\n')))
							claimed_rows += pane.width
							continue

						elif desired_width == EXPAND:
							growing_panes.append(pane)
							continue

			else:

				if element.hidden: continue

				if not element.geometry:
					element.width = 0
					continue

				desired_geometry = element.geometry[0]

				if element.coords and element.self_coordinating:
					rightmost = [element.coords[0][1][1],element.coords[1][1][1]]
					element.width = max(rightmost)
					continue

				if isinstance(desired_geometry, int):
					element.width = desired_geometry
					continue

				if isinstance(desired_geometry, str):
					if desired_geometry == FIT:
						buffer = ""
						for frame in element.content:
							buffer += frame[0]
						element.width = max(map(len, buffer.split('\n')))
					elif desired_geometry == EXPAND:
						element.width = self.width

			# Calculate the space to be shared between panes set to EXPAND
			remaining_space = self.width - claimed_rows
			for pane in growing_panes:
				pane.width = remaining_space / len(growing_panes)

		# Grant the first pane with height set to EXPAND an extra line if self.height is uneven:
		if self.height % 2:
			for pane in growing_panes:
				pane.height += 1
				break
	
		# Grant the rightmost panes an extra row if self.width is uneven:
		if self.width % 2:
			for pane in self.panes:
				if isinstance(pane, list):
					for i, p in enumerate(reversed(pane)):
						if i == 0 and not p.self_coordinating and p.geometry \
								and p.geometry[0] == EXPAND and not p.hidden:
								p.width += 1
				else:						
					if not pane.self_coordinating and pane.geometry \
						and pane.geometry[0] == EXPAND and not pane.hidden:
						pane.width += 1
						continue

		if self.debug:
			self.addstr(self.height-5, 0, "Window height: " + str(self.height))
			self.addstr(self.height-4, 0, "Window width:  " + str(self.width))
			self.addstr(self.height-2, 0, "Heights: " + str([p.height for p in self]))
			self.addstr(self.height-1, 0, "Widths:  " + str([p.width for p in self]))

	def coordinate(self, panes=[], index=0):
		"""
		Update pane coordinate tuples based on their height and width relative to other panes
		within the dimensions of the current window.

		Account for floating panes and self-coordinating panes adjacent to panes set to EXPAND.

		Coordinates are of the form:
		[
		  ((top-left-from-top, top-left-from-left),
		   (top-right-from-top, top-right-from-left)),
		  ((bottom-left-from-top, bottom-left-from-left),
		   (bottom-right-from-top, bottom-right-from-left))
		]

		We can then use these to determine things such as whether corners are inverted and how
		many characters may be drawn

		"""		
		y = 0 # height

		for i, element in enumerate(self.panes):
			x = 0 # width
			if isinstance(element, list):
				for j, pane in enumerate(element):
					if pane.hidden: continue
					current_width  = pane.width
					current_height = pane.height
					upper       = ((y, x), (y, x+current_width))
					lower       = ((y+current_height, x),
					               (y+current_height, x+current_width))
					pane.coords = [upper, lower]
					x += current_width
				y += current_height+1
			else:
				if element.hidden: continue
				current_width  = element.width
				current_height = element.height
				upper          = ((y, x), (y, x+current_width))
				lower          = ((y+current_height, x),
				                  (y+current_height, x+current_width))
				element.coords = [upper, lower]

				y += current_height+1

			if self.debug:
				coordinates = "Coordinates: " + str([p.coords for p in self])
				if len(coordinates) > self.width:
					coordinates = coordinates[:self.width - 3]
					coordinates += '...'
				self.addstr(self.height-3, 0, coordinates)

	def addstr(self, h, w, text, attrs=0):
		"""
		A safe addstr wrapper
		"""
		self.update_window_size()
		if h > self.height or w > self.width:
			return
		try:
			self.window.addstr(h, w, text, attrs)
		except Exception, e:
			pass

	def update_window_size(self):
		"""
		Update the current window object with its current
		height and width and clear the screen if they've changed.
		"""
		height, width = self.window.getmaxyx()
		if self.height != height or self.width != width:
			self.height, self.width = height, width
			self.window.clear()

	def add(self, pane):
		"""
		Adds new panes to the window
		"""
		if isinstance(pane, list):
			initialised_panes = []
			for p in pane:
				initialised_panes.append(self.init_pane(p))
			self.panes.append(initialised_panes)
		else:	
			pane = self.init_pane(pane)
			self.panes.append(pane)

	def init_pane(self, pane):
		if not pane.name:
			raise PaneError("Unnamed pane. How're you gonna move this thing around?")
		pane.active = True
		pane.window = self
		for existing_pane in self:
			if existing_pane.name == pane.name:
				raise WindowError("A pane is already attached with the name %s" % pane.name)
		return pane

	def block(self):
		self.window.blocking = True
		self.window.window.nodelay(0)

	def unblock(self):
		self.window.blocking = False
		self.window.window.nodelay(1)

	def get(self, name, default=None, cache=False):
		"""
		Get a pane by name, possibly from the cache. Return None if not found.
		"""
		if cache == True:
			for pane in self.cache:
				if pane.name == name:
					return pane
			return default
		for pane in self:
			if pane.name == name:
				return pane
		return default

	def __setitem__(self, name, new_pane):
		for i, pane in enumerate(self):
			if not isinstance(pane, list):
				if pane.name == name:
					self.panes[i] = new_pane
			else:
				for x, horiz_pane in enumerate(pane):
					if horiz_pane.name == name:
						self.panes[i][x] = new_pane
		raise KeyError("Unknown pane %s" % name)

	def __getitem__(self, name):
		for pane in self:
			if pane.name == name:
				return name
		raise KeyError("Unknown pane %s" % name)

	def __len__(self):
		return len([p for p in self])

	def __iter__(self):
		"""
		Iterate over self.panes by automatically flattening lists.
		"""
		panes = []
		for pane in self.panes:
			if type(pane) == list:
				panes.extend(pane)
			else:
				panes.append(pane)
		return iter(panes)

def palette(fg, bg=-1):
	"""
	Since curses only supports a finite amount of initialised colour pairs
	we memoise any selections you've made as an attribute on this function
	"""

	if not hasattr(palette, "counter"):
		palette.counter = 1

	if not hasattr(palette, "selections"):
		palette.selections = {}

	selection = "%s%s" % (str(fg), str(bg))
	if not selection in palette.selections:
		palette.selections[selection] = palette.counter
		palette.counter += 1

	# Get available colours
	colors = [c for c in dir(_curses) if c.startswith('COLOR')]
	if isinstance(fg, str):
		if not "COLOR_"+fg.upper() in colors:
			fg = -1
		else:
			fg = getattr(_curses, "COLOR_"+fg.upper())
	if isinstance(bg, str):
		if not "COLOR_"+bg.upper() in colors:
			bg = -1
		else:
			bg = getattr(_curses, "COLOR_"+bg.upper())

	_curses.init_pair(palette.selections[selection], fg, bg)
	return _curses.color_pair(palette.selections[selection])

class Pane(object):
	"""
	Subclassable data and logic for window panes.
	Panes can not be placed inside one another.

	The format for content is [text, alignment, attributes]. 
	text can contain newlines and will be printed as-is, overflowing by default.
	Multiple content elements can inhabit the same line and have different alignments.

	Panes can be marked as floating, instructing Window to draw any EXPANDing panes around them.
	"""
	name              = ''
	window            = None
	active            = None  # Whether this pane is accepting user input
	geometry          = []    # x,y (desired width, height)
	                          # Having a height of 1 makes your top and bottom coordinates identical.
	coords            = []    # [((top-left-from-top, top-left-from-left), (top-right-from-top, top-right-from-left)),
	                          #  ((bottom-left-from-top, bottom-left-from-left), (bottom-right-from-top, bottom-right-from-left))]
	content           = []    # [[text, align, attrs]] to render. Frames may hold multiple elements, displayed contiguously.
	height            = None  # Updated every cycle to hold the actual height
	width             = None  # Updated every cycle to hold the actual width
	attr              = None  # Default attributes to draw the pane with
	floating          = None  # Whether to float on top of adjacent EXPANDing panes
	self_coordinating = None  # Whether this pane defines its own coordinates
	wrap              = None  # Flow offscreen by default
	hidden            = None  # The default is to include panes in the draw() steps

	def __init__(self, name):
		"""
		We define self.content here so it's unique across instances.
		"""
		self.name = name
		self.content = []

	def process_input(self, character):
		"""
		A subclassable method for dealing with input characters.
		"""
		func = None
		try:
			func = getattr(self, "handle_%s" % chr(character), None)
		except:
			pass
		if func:
			func()

	def update(self):
		"""
		A subclassable method for updating content.
		Called on active panes in every cycle of the event loop.
		"""
		pass

	def change_content(self, index, text, align=ALIGN_LEFT, attrs=1):
		self.whoami = str(self)
		if index > len(self.content) and len(self.content): return
		if not self.content or index == len(self.content):
			self.content.append([text, align, attrs])
		else:
			self.content[index] = [text, align, attrs]

	def __repr__(self):
		if self.name:
			return "<Pane %s at %s>" % (self.name, hex(id(self)))
		return "<Pane at %s>" % hex(id(self))

class Menu(Pane):
	"""
	Defines a menu where items call local methods.
	"""
	geometry = [EXPAND, EXPAND]
	# Default and selection colours.
	col = [-1, -1] # fg, bg
	sel = [-1,  "blue"]
	items = []

	def update(self):
		for i, item in enumerate(self.items):
			if item[0]:
				colours = palette(self.sel[0], self.sel[1])
			else:
				colours = palette(self.col[0], self.col[1])
			text = ' ' + item[1]
			spaces = ' ' * (self.width - len(text)) 
			text += spaces
			self.change_content(i, text + '\n', ALIGN_LEFT, colours)

	def process_input(self, character):
		# Handle the return key
		if character == 10 or character == 13:
			for i, item in enumerate(self.items):
				if item[0]:	
					func = getattr(self, item[2].lower(), None)
					if func:
						func()

		# Handle navigating the menu
		elif character in [259, 258, 339, 338]:
			for i, item in enumerate(self.items):
				if item[0]:	
					if character == 259: # up arrow
						if i == 0: break
						item[0] = 0
						self.items[i-1][0] = 1
						break
					if character == 258: # down arrow
						if i+1 >= len(self.items): break
						item[0] = 0
						self.items[i+1][0] = 1
						break
					if character == 339: # page up
						item[0] = 0
						self.items[0][0] = 1
						break
					if character == 338: # page down
						item[0] = 0
						self.items[-1][0] = 1
						break

class Editor(Pane):
	"""
	Defines a text editor/input pane.
	"""
	geometry = [EXPAND, EXPAND]
	buffer = ""

	def update(self):
		if len(self.content) >= 1:
			self.change_content(1, "%i\n" % len(self.buffer))

	def process_input(self, character):
		self.window.window.clear()
		if character == 23 and self.buffer:      # Clear buffer on ^W
			self.buffer = ''
		if character == 263 and self.buffer:     # Handle backspace
			self.buffer = self.buffer[:-1]
		elif character == 10 or character == 13: # Handle the return key
			self.buffer += "\n"
		else:
			try: self.buffer += chr(character)   # Append input to buffer
			except: pass
		import random
		colours = palette(-1, random.choice(["blue","red"]))
		self.change_content(0, self.buffer, ALIGN_LEFT, colours)

class Pager(Pane):
	"""
	Defines a scrolling pager for long multi-line strings.
	"""
	geometry  = [EXPAND, EXPAND]
	data      = ""
	outbuffer = ""
	position  = 0

	def update(self):
		self.outbuffer = self.data.split('\n')[self.position:]
		self.change_content(1, '\n'.join(self.outbuffer))

	def process_input(self, character):
		if character == 259:                       # Up arrow
			if self.position != 0:
				self.position -= 1
		elif character == 258:                     # Down arrow
			self.position += 1
		elif character == 339:                     # Page up
			if self.position - self.height < 0:
				self.position = 0
			else:
				self.position -= self.height
		elif character == 338:                     # Page down
			if not self.position + self.height > len(self.data.split('\n')):
				self.position += self.height

