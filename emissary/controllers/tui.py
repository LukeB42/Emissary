import os
import time
from emissary.controllers.utils import tconv
from window import Window, Pane, ALIGN_LEFT, EXPAND, palette

class EmissaryMenu(Pane):
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
        # Handle the return key and the right arrow key
        if character == 10 or character == 13 or character == 261:
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

class FeedGroups(EmissaryMenu):
    geometry = [EXPAND, EXPAND]
    def update(self):
        if not self.items:
            (res, status) = self.window.c.get("feeds")
            

class Feeds(EmissaryMenu):
    geometry = [EXPAND, EXPAND]
    items = []


class Articles(Pane):
    """
    items for Articles are [1, "text", "uid"]
    """
    geometry = [EXPAND, EXPAND]
    items = []
    col = [-1, -1] # fg, bg
    sel = ["black",  "white"]
    avail = ["black", "green"]

    def update(self):
        if not self.items:
            self.fetch_items()

        for i, item in enumerate(self.items):
            if item[0]:
                if item[3]:
                    colours = palette(self.avail[0], self.avail[1])
                else:
                    colours = palette(self.sel[0], self.sel[1])
            else:
                colours = palette(self.col[0], self.col[1])
            text = ' ' + item[1]
            spaces = ' ' * (self.width - len(text)) 
            text += spaces
            self.change_content(i, text + '\n', ALIGN_LEFT, colours)

    def process_input(self, character):
        # Handle the return key and the right arrow key
        if character == 10 or character == 13 or character == 261:
            for i, item in enumerate(self.items):
                if item[0]:    
                    uid = item[2]
                    (article, status) = self.window.c.get('articles/' + uid)
                    statuspane = self.window.get("status")

                    if status != 200:
                        statuspane.status = str(status)
                    else:
                        self.reader.article = article
                        if article['content'] == None:
                            self.reader.data = ""
                        else:
                            self.reader.data = article['content']
                        self.reader.active = True
                        self.active = False

        elif character == 114:             # r to refresh
            self.fetch_items()

        elif character == 9:               # tab to reader
            self.reader.active = True
            self.active = False

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

    def fetch_items(self):
        (res, status) = self.window.c.get("articles?per_page=%i" % self.height)
        if status == 200:
            self.fill_menu(res)
        else:
            status = self.window.get("status")
            status.status = str(res)

    def fill_menu(self, res):
        self.items = []
        self.content = []
        for r in res["data"]:
            self.items.append([0, r['title'].encode("ascii", "ignore"), r['uid'], r['content_available']])
        if self.items:
            self.items[0][0] = 1

class Reader(Pane):
    """
    Defines a scrolling pager for long multi-line strings.
    """
    geometry  = [EXPAND, EXPAND]
    data      = ""
    outbuffer = ""
    position  = 0
    article   = None

    def update(self):
        if self.article:
            feed = self.article.get('feed', None)
            heading = "%s\n%s (%s ago)\n%s\n\n" % \
                (self.article['title'].encode("ascii","ignore"), feed if feed else "",
                tconv(int(time.time()) - int(self.article['created'])),
                self.article['url'])
            self.change_content(0, heading)
        self.outbuffer = self.data.split('\n')[self.position:]
        self.change_content(1, '\n'.join(self.outbuffer))

    def process_input(self, character):
        self.window.window.clear()
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

        elif character == 260 or character == 9:   # Left arrow or tab
            articles = self.window.get("articles")
            articles.active = True
            self.active = False

class StatusLine(Pane):
    geometry = [EXPAND, 1]
    content = []
    buffer = ""
    status = ""
    searching = False
#    tagline = "Psybernetics %s." % time.asctime().split()[-1]
    tagline = "Thanks God"

    def update(self):
        if self.searching:
            self.change_content(0, "/"+self.buffer, palette("black", "white"))
        else:
            state = self.tagline
            state += ' ' * ((self.width /2) - len(self.tagline) - (len(str(self.status))/2))
            state += str(self.status)
            self.change_content(0, state)

    def process_input(self, character):
        self.window.window.clear()
        if not self.searching and character == 47: # / to search
            articles = self.window.get("articles")
            articles.active = False
            self.searching = True
            return
        if self.searching:
            self.window.window.clear()
            if character == 23 and self.buffer:      # Clear buffer on ^W
                self.buffer = ''
            elif character == 263:                   # Handle backspace
                if self.buffer:
                    self.buffer = self.buffer[:-1]
                if not self.buffer:
                    self.searching = False
                    articles = self.window.get("articles")
                    articles.active = True

            elif character == 10 or character == 13:     # Handle the return key
                # Pass control back to the articles view
                self.searching = False
                articles = self.window.get("articles")
                articles.active = True
                self.buffer = ""
            else:
                try: self.buffer += chr(character)     # Append input to buffer
                except: pass
                # Perform a search for what's in the current buffer.
                articles = self.window.get("articles")
                url = "articles/search/"+self.buffer+"?per_page=" + str(articles.height)
                (res, status) = self.window.c.get(url)
                if status == 200:
                    articles.fill_menu(res)


window = Window(blocking=True)

feedgroups = FeedGroups("feedgroups")
feedgroups.active = False
feedgroups.hidden = True

feeds      = Feeds("feeds")
feeds.active = False
feeds.hidden = True

articles   = Articles("articles")

reader     = Reader("reader")
reader.wrap= True
reader.active = False

articles.reader = reader


status     = StatusLine("status")

panes = [feedgroups,feeds,articles,reader]
window.add(panes)
window.add(status)

window.exit_keys.append(4)
