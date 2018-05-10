#!/usr/bin/python3

from lib.dbconnection import DatabaseSession
from threading import Thread
from time import sleep
import os
import re

basedir = dir_path = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(basedir, '..', '.git', 'config'), 'r') as f:
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

    def _on_recv(self, channel, user, words):
        return self.on_recv(channel, user, words)

    def _on_trigger(self, channel, user, words=None):
        return self.on_trigger(channel, user, words)

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


class BuiltInConsole(BasePlugin):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prompt = ">>> "
        self.cmds = ['send', 'act']
        Thread(target=self.start).start()

    def start(self):
        while True:
            if self.client.load_complete:
                try:
                    execs = input(self.prompt)
                except KeyboardInterrupt:
                    break
                if execs:
                    split = execs.split()
                    cmd = split[0]
                    if cmd == 'send':
                        self.send_message(split)
                    elif cmd == 'act':
                        self.send_message(split, action=True)
            else:
                sleep(1)

    def send_message(self, split, action=False):
        try:
            chan = split[1]
            msg = ' '.join(split[2:])
        except IndexError:
            chan = None
            msg = None
        if chan and msg:
            self.client.send_channel_message(
                chan,
                msg,
                attachments=[],
                action=action
            )

    def on_recv(self, channel, user, words):
        pass


class BuiltInHelp(BasePlugin):

    hooks = ['list', 'help']
    help_pages = [
                {"list": "list - Lists registered hook commands"},
                {"help": "help <command> - Prints help for a command"},
            ]

    def recv_list(self):
        items = []
        for item in self.client.registered_hooks:
            items.append('`%s`' % item)
        commands = ', '.join(items)
        return "Loaded commands: %s" % commands

    def recv_help(self, words):
        try:
            command = words[1]
        except IndexError:
            return self.client.get_help_page('help')
        for item in self.client.help_pages:
            for key, value in item.items():
                if key == command:
                    return value
        return "I don't have a help page for that command"

    def on_recv(self, channel, user, words):
        if words[0] == 'list':
            return self.recv_list()
        elif words[0] == 'help':
            return self.recv_help(words)


class BuiltInReload(BasePlugin):

    hooks = ['reload']
    help_pages = [
                {"reload": "reload <users|config|plugins>\n\
                        Users - Slack User Database\n\
                        Config - Bot YAML Configuration\n\
                        Plugins - Bot Plugins"}
            ]

    def on_recv(self, channel, user, words):
        if words[0].lower() in self.hooks:
            try:
                target = words[1]
            except IndexError:
                return self.client.get_help_page('reload')
            if target.lower() == 'users':
                self.client._get_users()
                return "Reloaded User Data!"
            elif target.lower() == 'config':
                self.client._read_config()
                return "Reloaded Configuration!"
            elif target.lower() == 'plugins':
                self.client.dbsession = DatabaseSession()
                self.client._load_builtin_plugins()
                plugins = self.client._scrape_plugins()
                self.client._register_plugins(plugins)
                return "Reloaded Plugins!"
            else:
                return "I don't understand!"


class BuiltInSource(BasePlugin):

    hooks = ['source']
    help_pages = [
                {'source': 'Sends link to the bot source code'}
            ]
    trigger_phrases = ['show me your source']

    def on_trigger(self, channel, user, words):
        if self.get_trigger(words):
            return "View my source @ %s" % SOURCE

    def on_recv(self, channel, user, words):
        if words[0].lower() in self.hooks:
            return "View my source @ %s" % SOURCE


class BuiltInRestart(BasePlugin):

    hooks = ['restart']
    help_pages = [
                {"restart": "restart - Reboots the bot"}
            ]

    def on_recv(self, channel, user, words):
        if words[0].lower() in self.hooks:
            self.client.send_channel_message(channel, "Be back in a bit!")
            self.client._restart()


class BuiltInShutdown(BasePlugin):

    hooks = ['shutdown']
    help_pages = [
                {"shutdown": "shutdown - Shuts the bot down"}
            ]

    def on_recv(self, channel, user, words):
        if words[0].lower() in self.hooks:
            self.client.send_channel_message(channel, "Bye!")
            self.client._shutdown()


class BuiltInGreet(BasePlugin):

    hooks = ['greet']
    help_pages = [
                {"greet": "greet <@mention> - Greets a user by their name"}
            ]

    def on_recv(self, channel, user, words):
        if words[0].lower() in self.hooks:
            try:
                user = words[1]
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
