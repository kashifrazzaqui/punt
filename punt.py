#!/usr/bin/env python3
import sys, os
import configparser
import re
from collections import namedtuple
import sty
import subprocess
import random
from datetime import datetime, timedelta
from pathlib import Path
from itertools import cycle

# TODO: notifications
# TODO: theming
# TODO: start new file now - keybinding

NEWLINE = "\n"
COMMA = ","
COLON = ":"
SPACE = " "
RIGHT = ">"
WHITE = "white"
BLACK = "black"
GREY = "grey"
D_GREY = "da_grey"
L_GREY = "li_grey"
L_BLUE = "li_blue"
D_BLUE = "da_blue"
GREEN = "green"
L_YELLOW = "li_yellow"
D_YELLOW = "da_yellow"
L_BLACK = "li_black"
YELLOW = "yellow"
PINK = "li_magenta"
D_MAGENTA = "da_magenta"
MAGENTA = "magenta"
CYAN = "cyan"
RED = "red"
VERBOSE = "VRB"
DEBUG = "DBG"
INFO = "INF"
WARN = "WRN"
ERROR = "ERR"
FATAL = "FTL"
EXCEPTION_PATTERN = re.compile("java.*.Exception:")

PROC_RATE = 5  # checks /proc/status every 'n' seconds
FILE_SIZE_LINES = 20000

ENABLE_DEBUG_LOG = False
ENABLE_TRACING = False
ENABLE_STATUS_LINE = True
ENABLE_FILE_LOGGING = True


def log(message, *args):
    if ENABLE_DEBUG_LOG:
        print(">>>", message, *args)

def trace(message, flush_now=False):
    if ENABLE_TRACING:
        if flush_now:
            print(message, flush=flush_now)
            print("§", end=" ", flush=False)
        else:
            print(message, end=" ", flush=flush_now)


def pretty_time_delta(seconds):
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return '%dd%dh%dm%ds' % (days, hours, minutes, seconds)
    elif hours > 0:
        return '%dh%dm%ds' % (hours, minutes, seconds)
    elif minutes > 0:
        return '%dm%ds' % (minutes, seconds)
    else:
        return '%ds' % (seconds,)

class Color:
    @staticmethod
    def fg(s, color):
        return getattr(sty.fg, color) + s + sty.rs.fg

    @staticmethod
    def bg(s, color):
        return getattr(sty.bg, color) + s + sty.rs.bg

    @staticmethod
    def bold(s):
        return sty.ef.bold + s + sty.rs.bold_dim

    @staticmethod
    def this(s, bg_color, fg_color=WHITE):
        s = Color.fg(s, fg_color)
        return Color.bg(s, bg_color)


def _pad(s, width, fill_char=SPACE, align=RIGHT):
    return "{message:{fill}{align}{width}}".format(message=s, fill=fill_char, align=align, width=width)


def _format_log_level(level):
    if level == "V":
        level = Color.this(VERBOSE, GREY)
    elif level == "D":
        level = Color.this(DEBUG, L_BLUE)
    elif level == "I":
        level = Color.this(INFO, GREEN)
    elif level == "W":
        level = Color.this(WARN, PINK)
    elif level == "E":
        level = Color.this(ERROR, RED)
    elif level == "F":
        level = Color.this(INFO, RED)
    else:
        level = Color.this(level, BLACK)
    return Color.bold(level)


def formatter(color_dict):
    def _formatter(obj,tick_tock=0):
        #date = Color.fg(obj.date, color_dict["date"])
        truncated_time = obj.time[:10]
        time = Color.fg(truncated_time, color_dict["time"])
        pid = Color.fg(_pad(obj.pid, 5), color_dict["pid"])
        tid = Color.fg(_pad(obj.tid, 5), color_dict["tid"])
        level = _format_log_level(obj.level)
        truncated_tag = obj.tag[:40]
        tag = Color.fg(_pad(truncated_tag, 40), color_dict["tag"])
        #truncated_message = obj.message[:65]
        #if not truncated_message.endswith(NEWLINE):
        #    truncated_message += NEWLINE
        message = Color.fg(obj.message, color_dict["message"][tick_tock])
        return f"{time} {pid}({tid}) {tag} {level} {message}"

    return _formatter


color_dict = {"date": GREY, "time": L_GREY, "pid": D_GREY, "tid": D_GREY, "message": [L_GREY, YELLOW], "tag": L_BLUE}


def _raw_print(o):
    return f"{o.date} {o.time} {o.pid}({o.tid}) {o.level} #{o.line_no} {o.tag} {o.message}"


LogLine = namedtuple("LogLine", ["line_no", "date", "time", "pid", "tid", "level", "tag", "message"])
LogLine.print = formatter(color_dict)
LogLine.__str__ = _raw_print


def selector(select_patterns):
    def _pred(log_line):
        for p in select_patterns:
            tag_result = p.search(log_line.tag)
            if tag_result and tag_result.start() >= 0:
                return True
            else:
                message_result = p.search(log_line.message)
                if message_result and message_result.start() >= 0:
                    return True
        return False

    return _pred


def rejector(reject_patterns):
    def _pred(log_line):
        for p in reject_patterns:
            tag_result = p.search(log_line.tag)
            if tag_result and tag_result.start() >= 0:
                return True
            else:
                message_result = p.search(log_line.message)
                if message_result and message_result.start() >= 0:
                    return True
        return False

    return _pred


def status_line_fn():
    # icons = ['.','*','+','-','/']
    # icons= '\u2190,\u2191,\u2192,\u2193'.split(COMMA) #arrows
    # icons = '\u231b,\u23f3'.split(COMMA) #hour-glass
    icons = "\u2600,\u2601,\u2602,\u2603,\u2604,\u2605".split(COMMA)  # weather
    pool = cycle(icons)
    start_time = datetime.now()

    def fn(line, proc_lines, file_path, ex_count):
        if ENABLE_STATUS_LINE:
            process_data = ""
            if proc_lines:
                process_data = proc_lines[0][:-1]
            icon = next(pool)
            elapsed = datetime.now() - start_time
            elapsed = pretty_time_delta(elapsed.total_seconds())
            status_line = f"{icon} {elapsed} L{line.line_no} {file_path} {process_data} Exceptions:{ex_count}"
            status_line = Color.this(status_line, D_MAGENTA, WHITE)
            print(status_line, end="\r", flush=True)
    return fn


def _print():
    pool = cycle([0,1])
    def fn(line):
        sys.stdout.write("\033[K") # Clear to the end of line
        # the adb output already has a new line
        print(line.print(tick_tock=next(pool)), end="", flush=True)

    return fn


def _no_print(line):
    print(".", end="", flush=True)


def _relevant_log_level(log_line, targets):
    return True if log_line.level in targets else False


def _parse(line, line_no):
    ldate, ltime, lpid, ltid, llevel = line[:32].split()
    remaining = line[33:]
    colon_pos = remaining.find(COLON)
    if colon_pos > -1:
        ltag = remaining[:colon_pos]
        lline = remaining[colon_pos+1:]
    else:
        ltag = ""
        lline = remaining
    return LogLine(line_no, ldate, ltime, lpid, ltid, llevel, ltag, lline)


class Writer:
    def __init__(self, session_id, base_dir, lines_per_file=20000):
        t = datetime.today()
        self._sid = session_id
        self._today = f"{t.year}-{t.month}-{t.day}"
        self._enabled = False
        if not base_dir.endswith("/"):
            base_dir += "/"
        self._base_dir = base_dir
        self._current_file_sequence = 1
        self._line_count = 0
        self._file_size = lines_per_file
        self._truncate_marker = lines_per_file
        self._make_dir()
        self._open()
        log(f"File init done. {self._sid}|{self._base_dir}|{self.current_filename()}")

    def _dir_name(self):
        return self._base_dir + self._today + f"/{self._sid}"

    def _make_dir(self):
        Path(self._dir_name()).mkdir(parents=True, exist_ok=True)

    def current_filename(self, full=False):
        if full:
            return f"{self._dir_name()}/{self.current_filename()}"
        else:
            return f"log-{self._current_file_sequence}.txt"


    def _open(self):
        f_path = f"{self._dir_name()}/{self.current_filename()}"
        self._log_file = open(f_path, "w")

    def enable(self):
        self._enabled = True

    def close(self):
        self._log_file.flush()
        self._log_file.close()

    def write(self, line):
        if self._enabled:
            if self._line_count > self._truncate_marker:
                self._truncate_marker += self._file_size
                self.close()
                self._current_file_sequence += 1
                self._open()
            self._log_file.write(str(line))
            self._line_count += 1


def _proc_pid(pid):
    result = subprocess.run(["adb", "shell", "cat", f"/proc/{pid}/status"], stdout=subprocess.PIPE).stdout.decode(
        "utf-8"
    )
    l = result.replace("\t", "").replace("'", "").replace(" ", "").split("\n")
    d = dict((each.split(":") for each in l if len(each) > 1))
    s = f"PID-{pid} /proc/status: VM(Peak/HWM/RSS):({d['VmPeak']}/{d['VmHWM']}/{d['VmRSS']}) Threads:{d['Threads']}\n"
    return s


def get_proc_lines(pids):
    result = []
    for each in pids:
        result.append(_proc_pid(each))
    return result


class ProcessTracker:
    def __init__(self, packages=None):
        if packages:
            self._packages = packages
        else:
            self._packages = list()
        self._tracked_pids = set()
        self._update_tracked_pids()
        self._all_pids = set(self._tracked_pids)

    def _get_pid(self, package):
        result = subprocess.run(["adb", "shell", "pidof", package], stdout=subprocess.PIPE)
        pid = result.stdout.decode("utf-8")[:-1]
        return pid

    def _update_tracked_pids(self):
        pids = [self._get_pid(p) for p in self._packages]
        self._tracked_pids = set(pids)
        return self._tracked_pids

    def is_tracked(self, pid):
        if len(self._tracked_pids) == 0:
            return True
        if pid in self._tracked_pids:
            return True
        if pid in self._all_pids:
            return False
        # we seem to have a new pid
        # lets see if it for one of our tracked packages
        self._update_tracked_pids()
        if pid in self._tracked_pids:
            return True
        # seems to be a new process that we don't care about
        self._all_pids.add(pid)
        return False

    def get_tracked_pids(self):
        return self._tracked_pids

def has_exception(log_line):
    result = EXCEPTION_PATTERN.search(log_line.message)
    if result and result.start() >= 0:
        return True
    return False


def looper(session_id, lines, printer, writer, selector, rejector, target_levels, packages=None):
    """
    For any TRACKED process we print all lines - unless there is a rejectable regex.
    For any UNTRACKED process we reject all lines - unless there is selectable regex.
    """
    tracker = ProcessTracker(packages)
    exception_count = 0
    status_printer = status_line_fn()
    last_proc_ts = datetime.now()
    proc_lines = None
    for line_no, line in enumerate(lines, 1):
        current_file = writer.current_filename(full=True)
        try:
            delta = datetime.now() - last_proc_ts
            if delta.seconds > PROC_RATE:
                last_proc_ts = datetime.now()
                proc_lines = get_proc_lines(tracker.get_tracked_pids())
                writer.write(NEWLINE.join(proc_lines))

            log_line = _parse(line, line_no)
            if has_exception(log_line):
                exception_count += 1

            trace("PID: " + str(log_line.pid))
            if _relevant_log_level(log_line, target_levels):
                trace("relevant log level " + log_line.level)
                if tracker.is_tracked(log_line.pid):
                    trace("tracked")
                    if rejector:
                        trace("rejector defined")
                        if rejector(log_line):
                            trace("rejected to garbage", flush_now=True)
                            status_printer(log_line, proc_lines, current_file, exception_count)
                        else:
                            trace("could not reject", flush_now=True)
                            printer(log_line)
                            writer.write(log_line)
                    else:
                        trace("rejector undefined", flush_now=True)
                        printer(log_line)
                        writer.write(log_line)
                else:
                    trace("untracked")
                    if selector:
                        trace("selector defined")
                        if selector(log_line):
                            trace("selected", flush_now=True)
                            printer(log_line)
                            writer.write(log_line)
                        else:
                            trace("not selected off to garbage", flush_now=True)
                            status_printer(log_line, proc_lines, current_file, exception_count)
                    else:
                        trace("selector undefined off to garbage", flush_now=True)
                        status_printer(log_line,proc_lines, current_file, exception_count)
            else:
                trace("irrelevant log level " + log_line.level)
                status_printer(log_line, proc_lines, current_file, exception_count)
        except ValueError as e:
            trace("NOPARSE: " + line, flush_now=True)


def default_config():
    config = {"log_dir": "logs/", "file_size": FILE_SIZE_LINES}
    config["log_levels"] = "VIDWEF"
    return config


def _to_list(s):
    s = s.split(",")
    s = [each.strip() for each in s]
    return s


def _to_pattern(l):
    return [re.compile(pattern) for pattern in l]


def _convert_keys(config, convert_fn, keys):
    for k in keys:
        if k in config:
            config[k] = convert_fn(config[k])
    return config


def read_config(filepath):
    log("FilePath: ", filepath)
    result = default_config()
    if filepath:
        with open(filepath, "r") as f:
            config_string = "[X]\n" + f.read()
        config = configparser.ConfigParser()
        config.read_string(config_string)
        config = config._sections["X"]
        config = _convert_keys(config, _to_list, ["select", "reject"])
        config = _convert_keys(config, _to_pattern, ["select", "reject"])
        if "log_levels" in config:
            config["log_levels"] = config["log_levels"].upper()
        result.update(config)
        result["log_dir"] = os.path.expanduser(result["log_dir"])
        result["file_size"] = int(result["file_size"])
    else:
        log("No config file, continuing with defaults")
    return result


def _get_pid_packages(packages):
    result = packages.split(COMMA)
    log("packages", result)
    return result


def _get_filter_fns(config):
    s_fn, r_fn = None, None
    if "select" in config:
        if config["select"] == "*":
            s_fn = lambda x: True
        else:
            s_fn = selector(config["select"])
    if "reject" in config:
        if config["reject"] == "*":
            r_fn = lambda x: True
        else:
            r_fn = rejector(config["reject"])
    return s_fn, r_fn


def _new_session_id():
    return "%04x" % random.getrandbits(16)

def main(quiet=False):
    session_id = _new_session_id()
    log("Session name", session_id)
    config_filepath = os.path.expanduser(os.environ.get("PUNT_CONFIG", ""))
    config = read_config(config_filepath)
    log("Used config: ", config)
    if quiet:
        _print_fn = _no_print
    else:
        _print_fn = _print()

    pid_packages = []
    if "pids" in config:
        pid_packages = _get_pid_packages(config["pids"])
    s_fn, r_fn = _get_filter_fns(config)
    w = Writer(session_id, config["log_dir"], config["file_size"])
    if ENABLE_FILE_LOGGING:
        w.enable()

    try:
        looper(
            session_id,
            sys.stdin,
            printer=_print_fn,
            writer=w,
            selector=s_fn,
            rejector=r_fn,
            target_levels=config["log_levels"],
            packages=pid_packages,
        )
    except KeyboardInterrupt:
        log("\nEnding session name:", session_id)
        log("Used config: ", config)
        sys.exit(0)


if __name__ == "__main__":
    main(quiet=False)
