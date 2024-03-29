# punt
punt is a cli tool that makes `adb logcat` better.

```
adb logcat | punt.py
```

![Screenshot](https://github.com/kashifrazzaqui/punt/blob/main/punt_screenshot.png)

## Features
* Automatically track your apps logs even if the PID changes when your app crashes or restarts
* Save filters in a configuration file so you can easily switch between different configuration for different apps
* Run filters which are quite challenging to run on the adb logcat command line, two important use cases are
    * Select all log lines which are generated by your app but remove some specific matches (using simple strings or regex)
    * Select all log lines which are generated by other apps but have some specific matches (usings simple strings or regex)
* Automatically save logs for each session to disk - all day. Each line is prefixed with dir name of current logs for easy reference
* Select custom log levels such as just "verbose" and "fatal"
* Nice colored formatting on screen
* Track process memory usage, thread count and exceptions
* Easily save and reuse configuration/filters
* Highlights lines which are logging from UI/main thread
* Log only lines from UI/main thread


## Install

```
git clone git@github.com:kashifrazzaqui/punt.git punt
cd punt
pip install -r requirements.txt
```

## Configure
punt reads the PUNT_CONFIG environment variable for the full path of your config file, set it like so
```
export PUNT_CONFIG="~/.punt_configs/my_first_config.conf"
```
or set it up permanently in your bash/zshr file
if you want to change to another configuration, just export the path to PUNT_CONFIG and restart punt

### Sample config
```python
#your app package name
pids = com.me.myapp

#log lines from your package containing these words will be ignored
reject = words, or_comma_separated, regex_patterns

#these lines from untracked packages will additionally be included
select = words, or_regex

#your directory for saving logs; each time you start a punt session, it creates a new sub directory to save files under this
log_dir = ~/logs

 #chose which log levels you want, for example, no info is "vdwef"
log_levels = vdiwef

#each file is saved using format "log-n.txt" with so many lines per file
file_size = 25000

#select only logs printed on main thread (yes/no)
only_main_thread = yes
```

## Running
```
cd punt # directory where you cloned the git repo
chmod +x punt.py
adb logcat | punt.py
```

## Output format
`{time} {pid}({tid}) {tag} {level} {message}`

`session-id` is the name of the directory in which the current session log files are being saved - its 4 characters long.
for example, you can find the files in ~/logs/<session-id>/log-37.txt
