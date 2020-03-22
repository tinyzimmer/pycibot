#!/usr/bin/env python3
import os
import sys
import yaml
import inspect
import threading

from ..logging import SlackBotLogger as logger


def get_caller_name():
    caller = inspect.stack()[2][1]
    return caller.split("/")[-2]


class SlackBotConfig(object):

    @classmethod
    def build(cls, config_path=None):
        cls.config_path = config_path
        cls.config_stamp = os.stat(cls.config_path).st_mtime
        cls.ev = threading.Event()
        cls.change_funcs = []
        cls.load_config()
        # threading.Thread(target=cls.poll_config, daemon=True).start()

    @classmethod
    def load_config(cls):
        with open(cls.config_path, 'r') as f:
            data = yaml.safe_load(f.read())
            cls.config = data

    @classmethod
    def get(cls, key):
        caller_name = get_caller_name()
        if cls.config.get(caller_name, {}).get(key):
            return cls.config[caller_name][key]
        return None

    @classmethod
    def get_all(cls):
        caller_name = get_caller_name()
        return cls.config.get(caller_name)

    @classmethod
    def poll_config(cls):
        while True:
            if os.stat(cls.config_path).st_mtime != cls.config_stamp:
                logger.info("Detected change to config file, reloading")
                try:
                    cls.load_config()
                    for func in cls.change_funcs:
                        func()
                except Exception as err:
                    logger.error("Failed to reload configuration", err, sys.exc_info())
            cls.ev.wait(5)

    @classmethod
    def run_on_change(cls, f):
        cls.change_funcs.append(f)
        return f
