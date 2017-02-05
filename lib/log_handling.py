#!/usr/bin/env python2

from __future__ import print_function

import os
import sys
import time
import inspect
import getpass
import logging
from logging import handlers
from termcolor import colored

from common import InputValidationException

_filename = __file__


class LogManager:
    """
    Convenience class to manage the settings that I use most frequently for logging in Python
    """
    def __init__(self, name=None, entry_fmt=None, date_fmt=None, replace_handlers=True):
        entry_fmt = entry_fmt if entry_fmt is not None else "%(message)s"
        date_fmt = date_fmt if date_fmt is not None else "%Y-%m-%d %H:%M:%S %Z"
        self.tz_aliases = {"Eastern Standard Time": "EST", "Eastern Daylight Time": "EDT"}
        if (name is not None) and (len(logging._handlerList) < 1):  #Workaround for base logger defaulting to 30/WARNING
            logging.getLogger().setLevel(logging.NOTSET)
        self.logger = logging.getLogger(name)
        if replace_handlers:
            self.logger.handlers = []
        self.logger.setLevel(logging.NOTSET)    #Default is 30 / WARNING
        self.defaults = {"entry_format": entry_fmt, "date_format": date_fmt}
        for fn in ("debug", "info", "warning", "error", "critical", "exception", "log"):
            setattr(self, fn, getattr(self.logger, fn))
        self.add_level(19, "VERBOSE", "verbose")

    @classmethod
    def create_default_stream_logger(cls, debug=False, verbose=False, *args, **kwargs):
        """
        :param debug: True to log debug events to stdout, False to hide them
        :param args: Positional args to be passed to the LogManager constructor
        :param kwargs: Keyword args to be passed to the LogManager constructor
        :return: LogManager instance initialized with the default stream logger
        """
        lm = LogManager(*args, **kwargs)
        lm.init_default_stream_logger(debug, verbose)
        return lm

    @classmethod
    def create_default_logger(cls, debug=False, verbose=False, log_path=None, *args, **kwargs):
        """
        :param debug: True to log debug events to stdout, False to hide them
        :param log_path: Path to log file destination, otherwise a default filename is used
        :param args: Positional args to be passed to the LogManager constructor
        :param kwargs: Keyword args to be passed to the LogManager constructor
        :return: tuple(LogManager instance, actual log file path)
        """
        lm = LogManager(*args, **kwargs)
        actual_path = lm.init_default_logger(debug, verbose, log_path)
        return lm, actual_path

    def set_timezone_alias(self, original, alias):
        """
        :param original: Original string stored in time.tzname
        :param alias: String that should be used instead
        """
        self.tz_aliases[original] = alias

    @classmethod
    def create_filter(cls, filter_fn):
        """
        Uses the given function to filter log entries based on level number.  The function should return True if the
        record should be logged, or False to ignore it.
        :param filter_fn: A function that takes 1 parameter (level number) and returns a boolean
        :return: A custom, initialized subclass of logging.Filter using the given filter function
        """
        class CustomLogFilter(logging.Filter):
            def filter(self, record):
                return filter_fn(record.levelno)
        return CustomLogFilter()

    @classmethod
    def create_formatter(cls, should_format_fn, format_fn):
        """
        Example usage of an extra attribute: logging.error("Example message", extra={"red": True})
        :param should_format_fn: fn(record) that returns True for the format to be applied, False otherwise
        :param format_fn: fn(message) that returns the formatted message
        :return: A custom, uninitialized subclass of logging.Formatter
        """
        class CustomLogFormatter(logging.Formatter):
            def format(self, record):
                formatted = super(CustomLogFormatter, self).format(record)
                if should_format_fn(record):
                    formatted = format_fn(formatted)
                return formatted
        return CustomLogFormatter

    @classmethod
    def _prep_log_dir(cls, log_path, new_dir_permissions=0o1666):
        """
        Creates any necessary intermediate directories in order for the given log path to be valid
        :param log_path: Log file destination
        :param new_dir_permissions: Octal permissions for the new directory if it needs to be created.
        """
        log_dir = os.path.dirname(log_path)
        if os.path.exists(log_dir):
            if not os.path.isdir(log_dir):
                raise InputValidationException("Invalid log file dir - not a directory: {}".format(log_dir))
        else:
            os.makedirs(log_dir)
            if log_dir.startswith("/var/tmp/"):
                try:
                    os.chmod(log_dir, new_dir_permissions)
                except OSError:
                    pass

    def add_level(self, level_number, level_name, fn_name=None):
        """
        Example usage: lm.add_level(19, "VERBOSE", "verbose")
        :param level_number: Log level numeric value (10: debug, 20: info, 30: warning, 40: error, 50: critical)
        :param level_name: Name of the level to add to the logging module
        :param fn_name: (optional) Function name if not the same as level_name (becomes an attribute of this LogManager)
        """
        if level_name in logging._levelNames:
            val = logging._levelNames[level_name]
            raise InputValidationException("Log level called '{}' already exists: {}".format(level_name, val))
        elif level_number in logging._levelNames:
            val = logging._levelNames[level_number]
            raise InputValidationException("Log level {} already exists: {}".format(level_number, val))

        fn_name = fn_name if fn_name is not None else level_name
        try:
            getattr(self, fn_name)
        except AttributeError:
            logging.addLevelName(level_number, level_name)
            self._add_log_function(level_number, fn_name)
        else:
            raise InputValidationException("This LogManager already has a method called '{}'".format(fn_name))

    def _add_log_function(self, level_number, fn_name):
        """
        :param level_number: Log level numeric value (10: debug, 20: info, 30: warning, 40: error, 50: critical)
        :param fn_name: Function name to add to this LogManager instance
        """
        def _log(*args, **kwargs):
            self.logger.log(level_number, *args, **kwargs)
        setattr(self, fn_name, _log)

    def add_handler(self, destination, level=logging.INFO, fmt=None, date_fmt=None, filter=None, rotate=True, formatter=None):
        """
        :param destination: A stream or path destination for logged events
        :param level: Minimum log level for this logger
        :param fmt: Log entry format
        :param date_fmt: Format string for timestamps
        :param filter: An instance of logging.Filter
        :param rotate: Use TimedRotatingFileHandler when given a log path if True, otherwise use FileHandler
        :param formatter: Uninstantiated custom logging.Formatter class, otherwise logging.Formatter is used
        """
        entry_fmt = fmt if fmt is not None else self.defaults["entry_format"]
        date_fmt = date_fmt if date_fmt is not None else self.defaults["date_format"]
        formatter = formatter if formatter is not None else logging.Formatter

        if isinstance(destination, file) or (destination == sys.stdout) or (destination == sys.stderr):
            handler = logging.StreamHandler(destination)
        elif rotate:
            self._prep_log_dir(destination)
            handler = handlers.TimedRotatingFileHandler(destination, "midnight", backupCount=7)
        else:
            self._prep_log_dir(destination)
            handler = logging.FileHandler(destination)

        tz = time.strftime("%Z", time.localtime())
        if tz in self.tz_aliases:
            date_fmt = date_fmt.replace("%Z", self.tz_aliases[tz])

        handler.setLevel(level)
        handler.setFormatter(formatter(entry_fmt, date_fmt))
        if filter is not None:
            handler.addFilter(filter)
        self.logger.addHandler(handler)

    def init_default_stream_logger(self, debug=False, verbose=False):
        """
        Initialize a logger that sends INFO messages and below to stdout and WARNING messages and above to stderr
        :param bool debug: True to log debug events to stdout, False to hide them
        :param verbose: True to log verbose-level events to stdout, False to hide them
        """
        stderr_filter = self.create_filter(lambda lvl: lvl >= logging.WARNING)
        stdout_filter = self.create_filter(lambda lvl: lvl < logging.WARNING)
        stdout_lvl = logging.getLevelName("VERBOSE") if verbose else logging.INFO
        stdout_lvl = logging.DEBUG if debug else stdout_lvl
        red_formatter = self.create_formatter(lambda rec: getattr(rec, "red", False), lambda msg: colored(msg, "red"))
        self.add_handler(sys.stdout, stdout_lvl, filter=stdout_filter)
        self.add_handler(sys.stderr, fmt="%(levelname)s %(message)s", filter=stderr_filter, formatter=red_formatter)

    def init_default_logger(self, debug=False, verbose=False, log_path=None):
        """
        Initialize a logger that sends INFO messages and below to stdout and WARNING messages and above to stderr, and
        also saves all logs to a file.
        :param debug: True to log debug events to stdout, False to hide them
        :param verbose: True to log verbose-level events to stdout, False to hide them
        :param log_path: (optional) Path to log file destination, otherwise a default filename is used
        :return: Actual path that will be used for logging
        """
        self.init_default_stream_logger(debug, verbose)
        if log_path is None:
            try:
                calling_module = os.path.splitext(os.path.basename(inspect.getsourcefile(inspect.stack()[1][0])))[0]
            except TypeError:
                calling_module = "{}_interactive".format(os.path.splitext(os.path.basename(_filename))[0])
            log_path = "/var/tmp/{}_{}_{}.log".format(calling_module, getpass.getuser(), int(time.time()))
        file_fmt = "%(asctime)s %(levelname)s %(funcName)s:%(lineno)d %(message)s"
        self.add_handler(log_path, logging.DEBUG, file_fmt, rotate=True)
        return log_path
