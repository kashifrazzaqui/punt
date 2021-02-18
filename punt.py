#!/usr/bin/env python3
import sys, os
import configparser
import re
from collections import namedtuple
import sty
import subprocess

#TODO: Random session name
#TODO: File saving and rotation
#TODO: Profiling
#TODO: Bold selects
#TODO: build curses app
    #TODO: stats - selected/rejected lines
    #TODO: show dynamic current time
    #TODO: show config and pids etc

COMMA = ','
SPACE = ' '
RIGHT = '>'
WHITE = 'white'
BLACK = 'black'
GREY = 'grey'
D_GREY = 'da_grey'
L_BLUE = 'li_blue'
D_BLUE = 'da_blue'
GREEN = 'green'
L_YELLOW = 'li_yellow'
YELLOW = 'yellow'
PINK = 'li_magenta'
D_MAGENTA = 'da_magenta'
MAGENTA = 'magenta'
CYAN = 'cyan'
RED = 'red'
VERBOSE = 'VRB'
DEBUG = 'DBG'
INFO = 'INF'
WARN = 'WRN'
ERROR ='ERR'
FATAL = 'FTL'

ENABLE_LOGGING = True

def log(message, *args):
    if ENABLE_LOGGING:
        print('>>>',message, *args)

class Color:
    def fg(self, s, color):
        return getattr(sty.fg,color) + s + sty.rs.fg

    def bg(self, s, color):
        return getattr(sty.bg,color) + s + sty.rs.bg

    def bold(self, s):
        return sty.ef.bold + s + sty.rs.bold_dim

    def this(self, s, bg_color, fg_color=WHITE):
        s = self.fg(s, fg_color)
        return self.bg(s, bg_color)

def _pad(s, width,fill_char=SPACE, align=RIGHT):
    return '{message:{fill}{align}{width}}'.format(message=s,fill=fill_char, align=align,width=width)

def _format_log_level(color, level):
    if level == 'V':
        level = color.this(VERBOSE, GREY)
    elif level == 'D':
        level = color.this(DEBUG, L_BLUE)
    elif level == 'I':
        level = color.this(INFO, GREEN)
    elif level == 'W':
        level = color.this(WARN, PINK)
    elif level == 'E':
        level = color.this(ERROR, RED)
    elif level == 'F':
        level = color.this(INFO, RED)
    else:
        level = color.this(level, BLACK)
    return color.bold(level)

def formatter(color_dict):
    color = Color()
    def _formatter(obj):
        date = color.fg(obj.date, color_dict['date'])
        time = color.fg(obj.time, color_dict['time'])
        pid = color.fg(_pad(obj.pid, 5), color_dict['pid'])
        tid = color.fg(_pad(obj.tid, 5), color_dict['tid'])
        #level = color.fg(obj.level, D_BLUE)
        level = _format_log_level(color, obj.level)
        message = color.fg(obj.message, color_dict['message'])
        return f"{date} {time} {pid}({tid}) {level} {message}"
    return _formatter

color_dict = {'date':GREY, 'time':L_BLUE, 'pid':GREY, 'tid':D_GREY, 'message':WHITE}

LogLine = namedtuple('LogLine', ['line_no', 'date','time','pid','tid','level','message'])
LogLine.__str__ = formatter(color_dict)


def selector(select_patterns):
    def _pred(log_line):
        for p in select_patterns:
            result = p.search(log_line.log)
            if result and result.start() >= 0: return True
        return False
    return _pred

def rejector(reject_patterns):
    def _pred(log_line):
        for p in reject_patterns:
            result = p.search(log_line.message)
            if result and result.start() >= 0: return True
        return False
    return _pred

def garbage(line):
    pass

def _print(line):
    print(line, end='', flush=True)

def _no_print(line):
    print('.',end='',flush=True)

def _parse(line, line_no):
    ldate, ltime, lpid, ltid, llevel = line[:32].split()
    return LogLine(line_no, ldate, ltime, lpid, ltid, llevel, line[33:])


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
        result = subprocess.run(['adb','shell','pidof',package], stdout=subprocess.PIPE)
        pid = result.stdout.decode('utf-8')[:-1]
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


def looper(lines, printer, select_fn, reject_fn, packages=None):
    """
    For any TRACKED process we print all lines - unless there is a rejectable regex.
    For any UNTRACKED process we reject all lines - unless there is selectable regex.
    """
    tracker = ProcessTracker(packages)
    for line_no, line in enumerate(lines, 1):
        try:
            log_line = _parse(line, line_no)
            if tracker.is_tracked(log_line.pid):
                if reject_fn:
                    if reject_fn(log_line):
                        garbage(log_line)
                    else:
                        printer(log_line)
                else:
                    printer(log_line)
            else:
                if select_fn:
                    if select_fn(log_line):
                        printer(log_line)
                    else:
                        garbage(log_line)
                else:
                   garbage(log_line)
        except ValueError as e:
            log('NOPARSE:',line)

def default_config():
    config = {'log_dir':'logs/'}
    return config

def _to_list(s):
    s = s.split(',')
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
    log('FilePath: ', filepath)
    result = default_config()
    if filepath:
        with open(filepath, 'r') as f:
            config_string = '[X]\n' + f.read()
        config = configparser.ConfigParser()
        config.read_string(config_string)
        config = config._sections['X']
        config = _convert_keys(config, _to_list, ['select','reject'])
        config = _convert_keys(config, _to_pattern, ['select', 'reject'])
        result.update(config)
    else:
        log('No config file, continuing with defaults')
    return result

def _get_pid_packages(packages):
    result = packages.split(COMMA)
    log('packages',result)
    return result

def _get_filter_fns(config):
    s_fn, r_fn = None, None
    if 'select' in config:
        if config['select'] == '*':
            s_fn=lambda x: True
        else:
            s_fn = selector(config['select'])
    if 'reject' in config:
        if config['reject'] == '*':
            r_fn=lambda x: True
        else:
            r_fn = rejector(config['reject'])
    return s_fn, r_fn

def main(quiet=False):
    config_filepath = os.path.expanduser(os.environ.get('PUNT_CONFIG',''))
    config = read_config(config_filepath)
    if quiet:
        _print_fn = _no_print
    else:
        _print_fn = _print

    pid_packages = _get_pid_packages(config['pids'])
    s_fn, r_fn = _get_filter_fns(config)

    looper(sys.stdin, printer=_print_fn, select_fn=s_fn, reject_fn=r_fn, packages=pid_packages)

    log('\nEnding session name:')
    log('Used config: ', config)
    sys.exit(0)

if __name__ == '__main__':
    main(quiet=False)
