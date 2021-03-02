#!/usr/bin/env python3
import sys, os
import configparser
import re
from collections import namedtuple
import sty
import subprocess
import random
from datetime import datetime
from pathlib import Path
from itertools import cycle

# TODO: start new file now - keybinding

COMMA = ","
SPACE = " "
RIGHT = ">"
WHITE = "white"
BLACK = "black"
GREY = "grey"
D_GREY = "da_grey"
L_BLUE = "li_blue"
D_BLUE = "da_blue"
GREEN = "green"
L_YELLOW = "li_yellow"
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

PROC_RATE = 5  # seconds
FILE_SIZE_LINES = 20000

ENABLE_DEBUG_LOG = False
ENABLE_TRACING = False
ENABLE_GARBAGE = True
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


class Color:
    def fg(self, s, color):
        return getattr(sty.fg, color) + s + sty.rs.fg

    def bg(self, s, color):
        return getattr(sty.bg, color) + s + sty.rs.bg

    def bold(self, s):
        return sty.ef.bold + s + sty.rs.bold_dim

    def this(self, s, bg_color, fg_color=WHITE):
        s = self.fg(s, fg_color)
        return self.bg(s, bg_color)


def _pad(s, width, fill_char=SPACE, align=RIGHT):
    return "{message:{fill}{align}{width}}".format(message=s, fill=fill_char, align=align, width=width)


def _format_log_level(color, level):
    if level == "V":
        level = color.this(VERBOSE, GREY)
    elif level == "D":
        level = color.this(DEBUG, L_BLUE)
    elif level == "I":
        level = color.this(INFO, GREEN)
    elif level == "W":
        level = color.this(WARN, PINK)
    elif level == "E":
        level = color.this(ERROR, RED)
    elif level == "F":
        level = color.this(INFO, RED)
    else:
        level = color.this(level, BLACK)
    return color.bold(level)


def formatter(color_dict):
    color = Color()

    def _formatter(obj):
        date = color.fg(obj.date, color_dict["date"])
        time = color.fg(obj.time, color_dict["time"])
        pid = color.fg(_pad(obj.pid, 5), color_dict["pid"])
        tid = color.fg(_pad(obj.tid, 5), color_dict["tid"])
        level = _format_log_level(color, obj.level)
        message = color.fg(obj.message, color_dict["message"])
        return f"{date} {time} {pid}({tid}) {level} {message}"

    return _formatter


color_dict = {"date": GREY, "time": L_BLUE, "pid": GREY, "tid": D_GREY, "message": WHITE}


def _raw_print(o):
    return f"{o.date} {o.time} {o.pid}({o.tid}) {o.level} #{o.line_no} {o.message}"


LogLine = namedtuple("LogLine", ["line_no", "date", "time", "pid", "tid", "level", "message"])
LogLine.print = formatter(color_dict)
LogLine.__str__ = _raw_print


def selector(select_patterns):
    def _pred(log_line):
        for p in select_patterns:
            result = p.search(log_line.message)
            if result and result.start() >= 0:
                return True
        return False

    return _pred


def rejector(reject_patterns):
    def _pred(log_line):
        for p in reject_patterns:
            result = p.search(log_line.message)
            if result and result.start() >= 0:
                return True
        return False

    return _pred


def garbage_fn():
    # icons = ['.','*','+','-','/']
    # icons= '\u2190,\u2191,\u2192,\u2193'.split(COMMA) #arrows
    # icons = '\u231b,\u23f3'.split(COMMA) #hour-glass
    icons = "\u2600,\u2601,\u2602,\u2603,\u2604,\u2605".split(COMMA)  # weather
    pool = cycle(icons)

    def fn(line):
        if ENABLE_GARBAGE:
            print(">>", datetime.now().time(), next(pool), end="\r", flush=True)

    return fn


def _print(session_id):
    color = Color()

    def fn(line):
        sid = color.fg(f"{session_id}|", GREY)
        # the adb output already has a new line
        print(sid + line.print(), end="", flush=True)

    return fn


def _no_print(line):
    print(".", end="", flush=True)


def _relevant_log_level(log_line, targets):
    return True if log_line.level in targets else False


def _parse(line, line_no):
    ldate, ltime, lpid, ltid, llevel = line[:32].split()
    return LogLine(line_no, ldate, ltime, lpid, ltid, llevel, line[33:])


class Writer:
    def __init__(self, session_id, base_dir, lines_per_file=20000):
        t = datetime.today()
        self._sid = session_id
        self._today = f"{t.year}-{t.month}-{t.day}"
        if not base_dir.endswith("/"):
            base_dir += "/"
        self._base_dir = base_dir
        self._current_file_sequence = 1
        self._line_count = 0
        self._file_size = lines_per_file
        self._truncate_marker = lines_per_file
        self._make_dir()
        self._open()
        log(f"File init done. {self._sid}|{self._base_dir}|{self._current_filename()}")

    def _dir_name(self):
        return self._base_dir + self._today + f"/{self._sid}"

    def _make_dir(self):
        Path(self._dir_name()).mkdir(parents=True, exist_ok=True)

    def _current_filename(self):
        return f"log-{self._current_file_sequence}.txt"

    def _open(self):
        f_path = f"{self._dir_name()}/{self._current_filename()}"
        self._log_file = open(f_path, "w")

    def close(self):
        self._log_file.flush()
        self._log_file.close()

    def write(self, line):
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
    s = f"%%PROC%% PID-{pid}| VM-Peak:{d['VmPeak']}, VM-HWM:{d['VmHWM']}, VM-RSS:{d['VmRSS']}, Threads:{d['Threads']}\n"
    return s


def get_proc_lines(pids):
    result = []
    for each in pids:
        result.append(_proc_pid(each))
    return "\n".join(result)


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


def looper(lines, printer, writer, selector, rejector, target_levels, packages=None):
    """
    For any TRACKED process we print all lines - unless there is a rejectable regex.
    For any UNTRACKED process we reject all lines - unless there is selectable regex.
    """
    tracker = ProcessTracker(packages)
    garbage = garbage_fn()
    last_proc_ts = datetime.now()
    for line_no, line in enumerate(lines, 1):
        try:
            delta = datetime.now() - last_proc_ts
            if delta.seconds > PROC_RATE:
                last_proc_ts = datetime.now()
                proc_lines = get_proc_lines(tracker.get_tracked_pids())
                print(proc_lines)
                writer(proc_lines)

            log_line = _parse(line, line_no)
            trace("PID: " + str(log_line.pid))
            if _relevant_log_level(log_line, target_levels):
                trace("relevant log level " + log_line.level)
                if tracker.is_tracked(log_line.pid):
                    trace("tracked")
                    if rejector:
                        trace("rejector defined")
                        if rejector(log_line):
                            trace("rejected to garbage", flush_now=True)
                            garbage(log_line)
                        else:
                            trace("could not reject", flush_now=True)
                            printer(log_line)
                            writer(log_line)
                    else:
                        trace("rejector undefined", flush_now=True)
                        printer(log_line)
                        writer(log_line)
                else:
                    trace("untracked")
                    if selector:
                        trace("selector defined")
                        if selector(log_line):
                            trace("selected", flush_now=True)
                            printer(log_line)
                            writer(log_line)
                        else:
                            trace("not selected off to garbage", flush_now=True)
                            garbage(log_line)
                    else:
                        trace("selector undefined off to garbage", flush_now=True)
                        garbage(log_line)
            else:
                trace("irrelevant log level " + log_line.level)
                garbage(log_line)
        except ValueError as e:
            trace("NOPARSE: " + line, flush_now=True)


def default_config():
    config = {"log_dir": "logs/", "file_size": FILE_SIZE_LINES}
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
        else:
            config["log_levels"] = "VIDWEF"
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


def writer_fn(session_id, log_dir, file_size):
    w = Writer(session_id, log_dir, file_size)

    def fn(line):
        try:
            w.write(line)
        except Exception as e:
            print("Caught exception when writing", e)
            w.close()
            sys.exit(1)

    return fn


def _no_write(line):
    pass


def main(quiet=False):
    session_id = _new_session_id()
    log("Session name", session_id)
    config_filepath = os.path.expanduser(os.environ.get("PUNT_CONFIG", ""))
    config = read_config(config_filepath)
    log("Used config: ", config)
    if quiet:
        _print_fn = _no_print
    else:
        _print_fn = _print(session_id)

    pid_packages = []
    if "pids" in config:
        pid_packages = _get_pid_packages(config["pids"])
    s_fn, r_fn = _get_filter_fns(config)
    # 100K lines is about 13M
    w_fn = _no_write
    if ENABLE_FILE_LOGGING:
        w_fn = writer_fn(session_id, config["log_dir"], config["file_size"])

    try:
        looper(
            sys.stdin,
            printer=_print_fn,
            writer=w_fn,
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
