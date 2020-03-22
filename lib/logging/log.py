#!/usr/bin/env python3
import sys
import traceback
from datetime import datetime
from inspect import getframeinfo, stack


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


def format_with_opts(message, format_opts=[]):
    out = ""
    formatted = False
    for opt in format_opts:
        attr =  getattr(Colors, opt.upper())
        if attr:
            out += attr
            formatted = True
    out += str(message)
    if formatted:
        out += Colors.RESET
    return out


def debugwrite(header, message, idx=2):
    caller = getframeinfo(stack()[idx][0])
    fname = '/'.join(caller.filename.split('/')[-3:])
    src = f"{fname}:{caller.lineno}"
    out = f"{header}{' '* (16-len(header))}{Colors.BOLD}{src}{Colors.RESET} - {str(datetime.now())} - {message}\n"
    sys.stdout.write(out)
    sys.stdout.flush()


DEBUG = False


class SlackBotLogger(object):

    @classmethod
    def build(cls, config):
        global DEBUG
        cls.on_print_funcs = []
        if config.get('debug') is True:
            DEBUG = True

    @classmethod
    def info(cls, msg, format_opts=[]):
        debugwrite(
            f"{Colors.HEADER}INFO:{Colors.RESET}",
            f"{format_with_opts(msg, format_opts=format_opts)}"
        )
        cls.run_event_funcs(msg)

    @classmethod
    def debug(cls, msg, format_opts=[]):
        if DEBUG:
            debugwrite(
                f"{Colors.BLUE}DEBUG:{Colors.RESET}",
                f"{format_with_opts(msg, format_opts=format_opts)}"
            )
            cls.run_event_funcs(msg)

    @classmethod
    def error(cls, msg, err, exc_info=None):
        traceback.print_exception(*exc_info)
        debugwrite(
            f"{Colors.FAIL}ERROR:{Colors.RESET}",
            f"{msg}: {str(err)}"
        )
        cls.run_event_funcs(msg)
        del exc_info

    @classmethod
    def on_log(cls, f):
        cls.on_print_funcs.append(f)
        return f

    @classmethod
    def run_event_funcs(cls, msg):
        for func in cls.on_print_funcs:
            func(msg)
