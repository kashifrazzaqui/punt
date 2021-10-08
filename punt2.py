import curses
import collections

BuildSpec = collections.namedtuple('BuildSpec', 'name, percent_height, percent_width, is_pad, pad_height, pad_width')


class Window:
    def __init__(self, stdscr, name, height, width, begin_x, begin_y):
        self.name = name
        self.height = int(height)
        self.width = int(width)
        self._stdscr = stdscr
        self.window = self._stdscr.subwin(self.height, self.width, int(begin_y), int(begin_x))
        self._has_border = False

    def add_border(self):
        self._has_border = True

    def has_border(self):
        return self._has_border

    def __getattr__(self, name):
        return getattr(self.window, name)


class Pad(Window):
    def __init__(self, stdscr, name, view_height, view_width, height, width, top_left_x, top_left_y):
        self.name = name
        self.height = int(height)
        self.width = int(width)
        self.tl_x = int(top_left_x)
        self.tl_y = int(top_left_y)
        self.br_x = int(top_left_x + view_width) - 1
        self.br_y = int(top_left_y + view_height) - 2
        self._stdscr = stdscr
        self.window = curses.newpad(self.height, self.width)
        self._has_border = False
        self._pos = 0

    def refresh(self, pad_x=None, pad_y=None):
        if pad_y == None:
            pad_y = self._pos
        self.window.refresh(pad_y, 0, self.tl_y, self.tl_x, self.br_y, self.br_x)

    def scroll_to(self, pos=0):
        self._pos = pos
        self.window.refresh(self._pos, 0, self.tl_y, self.tl_x, self.br_y, self.br_x)

    def scroll_up(self):
        self._pos = self._pos - 1 if self._pos > 0 else 0
        self.window.refresh(self._pos, 0, self.tl_y, self.tl_x, self.br_y, self.br_x)

    def scroll_down(self):
        self._pos = self._pos + 1 if self._pos < self.height else self.height
        self.window.refresh(self._pos, 0, self.tl_y, self.tl_x, self.br_y, self.br_x)


class Layout:
    FILL_WIDTH = -10
    FILL_HEIGHT = -20

    def __init__(self, stdscr):
        self._build_list = []
        self._windows = {}
        self._has_status_bar = False
        self._stdscr = stdscr

    def compute_screen_size(self):
        curses.update_lines_cols()
        self.height, self.width = self._stdscr.getmaxyx()
        if self._has_status_bar:
            self.height = self.height - 1

    def place(self):
        """
        for win in self._windows.values():
            del win
        """
        self._windows = {}
        self.compute_screen_size()

        if self._has_status_bar:
            self.status_bar = Window(self._stdscr, 'status_bar', 1, self.width, 0, self.height-1)
            self._windows['status_bar'] = self.status_bar

        begin_x, begin_y = 0, 0
        end_x, end_y = 0, 0
        row_available = 1.0
        for spec in self._build_list:
            abs_height = self.height * spec.percent_height
            abs_width = self.width * spec.percent_width

            # TODO: add support for FILL_HEIGHT
            if spec.percent_width != Layout.FILL_WIDTH:  # is it specified or a fill remaing space
                if spec.percent_width <= row_available:  # is there enough space in this row
                    begin_x = end_x
                    row_available -= spec.percent_width
                    end_x = begin_x + abs_width
                    end_y = begin_y + abs_height
                else:
                    row_available = 1.0  # new row
                    begin_y = end_y
                    begin_x = 0
                    end_x = begin_x + abs_width
                    end_y = begin_y + abs_height
                    row_available -= spec.percent_width
            else:  # just make it as big as it can be in this row
                abs_width = self.width * row_available
                row_available = 0
                begin_x = end_x
                end_x = begin_x + abs_width
                end_y = begin_y + abs_height

            if spec.is_pad:
                self._windows[spec.name] = Pad(self._stdscr, spec.name, abs_height, abs_width, spec.pad_height, spec.pad_width,
                                               begin_x, begin_y)
            else:
                self._windows[spec.name] = Window(self._stdscr, spec.name, abs_height, abs_width, begin_x, begin_y)
        return self._windows

    def refresh(self, clear=False):
        for win in self._windows.values():
            if isinstance(win, Window):
                if clear:
                    win.clear()
                if win.has_border():
                    win.box()
                win.refresh()

    def touchwin(self):
        for win in self._windows.values():
            win.touchwin()
        self._stdscr.touchwin()

    def resizeterm(self):
        curses.update_lines_cols()
        curses.resizeterm(*self._stdscr.getmaxyx())
        self._stdscr.clear()
        self.touchwin()
        self.refresh()

    def add_status_bar(self):
        self._has_status_bar = True

    def add_window(self, name, percentage_height, percentage_width):
        self._build_list.append(BuildSpec(name, percentage_height, percentage_width, False, 0, 0))

    def add_pad(self, name, percentage_height, percentage_width, pad_height, pad_width):
        self._build_list.append(BuildSpec(name, percentage_height, percentage_width, True, pad_height, pad_width))


def make_windows(stdscr, layout):
    layout.add_window('left_panel', 0.2, 0.5)
    layout.add_window('right_panel', 0.2, 0.5)
    layout.add_pad('log_view', 0.8, 1, 10000, 200)
    layout.add_status_bar()
    windows = layout.place()

    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_GREEN)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_MAGENTA)
    windows['status_bar'].bkgd(curses.color_pair(1))
    windows['left_panel'].bkgd(curses.color_pair(2))
    windows['right_panel'].bkgd(curses.color_pair(3))
    windows['log_view'].bkgd(curses.color_pair(4))
    return windows


def looper(layout, windows):
    k = ''
    lp = windows['left_panel']
    rp = windows['right_panel']
    lv = windows['log_view']
    sb = windows['status_bar']
    lp_title = f"{lp.name} {lp.width} {lp.height}"
    rp_title = f"{rp.name} {rp.width} {rp.height}"
    sb_title = f"{sb.name} {sb.width} {sb.height}"
    sb_body = f"{lp.getbegyx()} {rp.getbegyx()} {sb.getbegyx()}"

    for each in range(1,100):
        lv.addstr(each, 0, f"{lv.br_x} {lv.br_y} --- {each}")
    lv.scroll_to(100)

    while k != ord('q'):
        lp.addstr(0, 0, lp_title)
        lp.addstr(2, 0, rp_title)
        lp.addstr(4, 0, sb_title)
        lp.addstr(6, 0, str(len(windows)))
        k = lv.getch()
        if lv._pos < 0 or lv._pos > 900:
            sb.addstr(0,0, "----***------")
        else:
            sb.addstr(0,0, str(lv._pos))
        layout.refresh()
        if k == curses.KEY_RESIZE:
            return True
        if  k == curses.KEY_DOWN or k == 66:
            lv.scroll_down()
        elif k == curses.KEY_UP or k == 65:
            lv.scroll_up()
    return False


def curses_main(stdscr):
    curses.halfdelay(1)
    layout = Layout(stdscr)
    windows = make_windows(stdscr, layout)
    while looper(layout, windows):
        layout = Layout(stdscr)
        layout.resizeterm()
        windows = make_windows(stdscr, layout)
        layout.refresh()


def main():
    curses.wrapper(curses_main)


if __name__ == "__main__":
    main()
