#!/usr/bin/python3

from lib.builtins import BasePlugin
import random
import os

basedir = os.path.dirname(os.path.realpath(__file__))
excuse_path = os.path.join(basedir, 'excuses.txt')


class SlackBotPlugin(BasePlugin):

    hooks = ['excuse']
    help_pages = [{'excuse': 'excuse - grab a random excuse'}]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._populate_excuses()

    def _populate_excuses(self):
        with open(excuse_path, 'r') as f:
            data = f.read()
        self.excuses = data.splitlines()

    def on_trigger(self, channel, user, words):
        pass

    def on_recv(self, channel, user, words):
        if words[0] == 'excuse':
            secure_random = random.SystemRandom()
            return secure_random.choice(self.excuses).strip()
