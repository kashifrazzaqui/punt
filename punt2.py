import curses
import collections

BuildSpec = collections.namedtuple('BuildSpec', 'name, ph, pw')


class Window:
    def __init__(self, height, width, begin_x, begin_y):
        #TODO: add name
        #TODO: add pad support
        self.window = curses.newwin(int(height), int(width), int(begin_y), int(begin_x))
        self._has_border = False

    def add_border(self):
        self._has_border = True

    def has_border(self):
        return self._has_border

    def __getattr__(self, name):
        return getattr(self.window, name)


class Layout:
    def __init__(self, stdscr):
        self._build_list = []
        self._windows = {}
        self._has_status_bar = False
        self._stdscr = stdscr

    def compute_screen_size(self):
        self.height, self.width = self._stdscr.getmaxyx()
        if self._has_status_bar:
            self.height = self.height - 1

    def build(self):
        self.compute_screen_size()
        # TODO: delete existing windows - call `del win` to delete
        if self._has_status_bar:
            self.status_bar = Window(2, self.width, 0, self.height-1)
            self._windows['status_bar'] = self.status_bar

        begin_x, begin_y = 0, 0
        end_x, end_y = 0, 0
        row_available = 1.0
        for spec in self._build_list:
            abs_height = self.height * spec.ph
            abs_width = self.width * spec.pw

            if spec.pw > 0:  # is it specified or a fill remaing space
                if spec.pw <= row_available:  # is there enough space in this row
                    begin_x = end_x
                    row_available -= spec.pw
                    end_x = begin_x + abs_width
                    end_y = begin_y + abs_height
                else:
                    row_available = 1.0  # new row
                    begin_y = end_y
                    begin_x = 0
                    end_x = begin_x + abs_width
                    end_y = begin_y + abs_height
                    row_available -= spec.pw
            else:  # just make it as big as it can be in this row
                """
                Edge case not handled: if you have a window remaining to put which is a "fill-width"
                and row_available is already '0', then this window will be invisible
                """
                abs_width = self.width * row_available
                row_available = 0
                begin_x = end_x
                end_x = begin_x + abs_width
                end_y = begin_y + abs_height

            self._windows[spec.name] = Window(abs_height, abs_width, begin_x, begin_y)
        return self._windows

    def refresh(self, clear=False):
        for win in self._windows.values():
            if clear:
                win.clear()
            if win.has_border():
                win.box()
            win.refresh()

    def add_status_bar(self):
        self._has_status_bar = True

    def add_window(self, name, percentage_height, percentage_width):
        self._build_list.append(BuildSpec(name, percentage_height, percentage_width))


def make_windows(stdscr, layout):
    layout.add_window('left_panel', 0.2, 0.5)
    layout.add_window('right_panel', 0.2, 0.5)
    #layout.add_pad('log_view', 0, 1)
    layout.add_status_bar()
    windows = layout.build()

    for w in windows.values():
        w.box()

    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_GREEN)
    windows['status_bar'].bkgd(curses.color_pair(1))
    windows['left_panel'].bkgd(curses.color_pair(2))
    windows['right_panel'].bkgd(curses.color_pair(3))
    return windows


def looper(layout, windows):
    k = ''
    lp = windows['left_panel']
    rp = windows['right_panel']
    sb = windows['status_bar']
    while k != ord('q'):
        lp.addstr(0, 0, str(len(windows.values())))
        rp.addstr(1, 0, "rp")
        sb.addstr(0, 0, "sb")
        k = lp.getch()
        layout.refresh()
        if k == curses.KEY_RESIZE:
            return True
    return False


def curses_main(stdscr):
    layout = Layout(stdscr)
    windows = make_windows(stdscr, layout)
    layout.refresh()
    while looper(layout, windows):
        pass


def main():
    curses.wrapper(curses_main)


if __name__ == "__main__":
    main()