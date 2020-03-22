#!/usr/bin/python3

from threading import Thread
from time import sleep
import os
import re

basedir = dir_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(basedir, '..', '..', '.git', 'config'), 'r') as f:
    git_config = f.read()
    SOURCE = re.search(
            'url = (.*)',
            git_config
            ).groups()[0].replace(':', '/').replace('git@', 'https://')


class BasePlugin(object):

    def __init__(self, client):
        self.client = client
        try:
            if self.hooks:
                if isinstance(self.hooks, list):
                    self.hooks = self.hooks
        except Exception:
            pass
        try:
            if self.help_pages:
                if isinstance(self.help_pages, list):
                    self.help_pages = self.help_pages
        except Exception:
            pass
        try:
            if self.trigger_phrases:
                if isinstance(self.trigger_phrases, list):
                    self.trigger_phrases = self.trigger_phrases
        except Exception:
            pass

    def _on_recv(self, channel, user, cmd, words):
        return self.on_recv(channel, user, cmd, words)

    def _on_trigger(self, channel, user, words):
        return self.on_trigger(channel, user, words)

    def _on_context(self, channel, user, ctx, words):
        return self.on_context(channel, user, ctx, words)

    def _setUp(self):
        return self.setUp()

    def get_trigger(self, words):
        message = ' '.join(words).lower()
        triggers = [
                x for x in self.trigger_phrases
                if x in message
                ]
        if len(triggers) > 0:
            trigger = triggers[-1]
        else:
            trigger = None
        return trigger


class BuiltInHelp(BasePlugin):

    hooks = ['list', 'help']
    help_pages = [
                {"list": "list - Lists registered hook commands"},
                {"help": "help <command> - Prints help for a command"},
            ]

    def recv_list(self):
        items = []
        for item in self.client.plugins.get_all_hooks():
            items.append('`%s`' % item)
        commands = ', '.join(items)
        return "Loaded commands: %s" % commands

    def recv_help(self, words):
        try:
            command = words[0]
        except IndexError:
            return self.client.get_help_page('help')
        help_page = self.client.get_help_page(command)
        if help_page:
            return help_page
        return "I don't have a help page for that command"

    def on_recv(self, channel, user, cmd, words):
        if cmd == 'list':
            return self.recv_list()
        elif cmd == 'help':
            return self.recv_help(words)


class BuiltInReload(BasePlugin):

    hooks = ['reload']
    help_pages = [
                {"reload": "reload <users|config|plugins>\n\
                        Users - Slack User Database\n\
                        Config - Bot YAML Configuration\n\
                        Plugins - Bot Plugins"}
            ]

    def on_recv(self, channel, user, cmd, words):
        if cmd == 'reload':
            return "This functionality is broken at the moment"


class BuiltInSource(BasePlugin):

    hooks = ['source']
    help_pages = [
                {'source': 'Sends link to the bot source code'}
            ]
    trigger_phrases = ['show me your source']

    def on_trigger(self, channel, user, words):
        if self.get_trigger(words):
            return "View my source @ %s" % SOURCE

    def on_recv(self, channel, user, cmd, words):
        if cmd == 'source':
            return "View my source @ %s" % SOURCE


class BuiltInRestart(BasePlugin):

    hooks = ['restart']
    help_pages = [
                {"restart": "restart - Reboots the bot"}
            ]

    def on_recv(self, channel, user, cmd, words):
        if cmd == 'restart':
            self.client.send_channel_message(channel, "Be back in a bit!")
            self.client.restart()


class BuiltInShutdown(BasePlugin):

    hooks = ['shutdown']
    help_pages = [
                {"shutdown": "shutdown - Shuts the bot down"}
            ]

    def on_recv(self, channel, user, cmd, words):
        if cmd == 'shutdown':
            self.client.send_channel_message(channel, "Bye!")
            self.client.shutdown()


class BuiltInGreet(BasePlugin):

    hooks = ['greet']
    help_pages = [
                {"greet": "greet <@mention> - Greets a user by their name"}
            ]

    def on_recv(self, channel, user, cmd, words):
        if cmd == 'greet':
            try:
                user = words[0]
            except IndexError:
                return self.client.get_help_page('greet')
            user_id = self.client.sanitize_handle(user)
            response = None
            user_profile = self.client.get_user_profile(user_id)
            if user_profile:
                response = "Hiya %s, nice to meet you!" % (
                        user_profile['real_name']
                        )
                return response
