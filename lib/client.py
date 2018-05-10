#!/usr/bin/python3

from lib.exceptions import \
        ConfigParsingError, \
        InvalidCredentials, InvalidPlugin, InvalidResponseFromPlugin, \
        MissingBotName, MissingSlackToken
from lib.builtins import \
        BuiltInHelp, BuiltInReload, BuiltInRestart, BuiltInShutdown, \
        BuiltInGreet, BuiltInSource, BuiltInConsole
from lib.dbconnection import DatabaseSession
from lib.colors import colors
from slackclient import SlackClient
from threading import Thread
from time import sleep
import os
import sys
import yaml
import importlib.util
import traceback

basedir = os.path.dirname(os.path.realpath(__file__))


class SlackBot(object):

    def __init__(self):
        sys.stdout.write(
                "%sStarting up Slack Bot\n%s" % (
                        colors.HEADER,
                        colors.RESET
                    )
                )
        sys.stdout.flush()
        self.base_path = os.path.join(basedir, '..')
        self.config_path = os.path.join(self.base_path, 'config.yml')
        self.dbsession = DatabaseSession()
        self.__bootstrap()

    def __bootstrap(self):
        self.running = True
        self.load_complete = False
        sys.stdout.write(
                "Loading configuration and testing Slack credentials..."
                )
        sys.stdout.flush()
        self.__load_config()
        sys.stdout.write("Done!\n")
        sys.stdout.write("Loading Plugins...\n")
        sys.stdout.flush()
        self.builtins = [
                ('help', BuiltInHelp),
                ('reload', BuiltInReload),
                ('restart', BuiltInRestart),
                ('shutdown', BuiltInShutdown),
                ('greet', BuiltInGreet),
                ('source', BuiltInSource),
                ('console', BuiltInConsole)
                ]
        self._load_builtin_plugins()
        plugins = self._scrape_plugins()
        self._register_plugins(plugins)
        self.users = self._get_users()
        self.bot_id = self._get_my_id()
        self.display_name = self.get_user_profile(self.bot_id)['name']
        self.at_bot = "<@" + self.bot_id + ">"
        sys.stdout.write(
                "%sInitialization Complete!\n%s" % (
                    colors.OKGREEN,
                    colors.RESET
                )
            )
        sys.stdout.flush()
        self.load_complete = True
        self.start_bot()

    def __load_config(self):
        self._read_config()
        self.__verify_config()
        self.__test_credentials()

    def __verify_config(self):
        try:
            self.name = self.config['bot_name']
        except KeyError:
            raise MissingBotName
        try:
            self.client = SlackClient(self.config['slack_token'])
        except KeyError:
            raise MissingSlackToken
        try:
            self.admins = self.config['admins']
        except KeyError:
            pass

    def __test_credentials(self):
        if self.client.rtm_connect():
            return True
        else:
            raise InvalidCredentials

    def _load_builtin_plugins(self):
        self.registered_plugins = {}
        self.trigger_plugins = {}
        self.trigger_phrases = []
        self.registered_hooks = []
        self.help_pages = []
        for item in self.builtins:
            key, plugin = item
            loaded = plugin(client=self)
            self.registered_plugins[key] = loaded
            try:
                for item in loaded.hooks:
                    self.registered_hooks.append(item)
            except AttributeError:
                pass
            try:
                for item in loaded.help_pages:
                    for command, chelp in item.items():
                        self.help_pages.append(
                            {command: chelp}
                        )
            except AttributeError:
                pass
            try:
                for item in loaded.trigger_phrases:
                    self.trigger_phrases.append(item)
                    self.trigger_plugins[key] = loaded
            except AttributeError:
                pass
            sys.stdout.write(
                    "%sRegistered builtin plugin: %s\n%s" % (
                            colors.OKGREEN,
                            key,
                            colors.RESET
                        )
                    )
            sys.stdout.flush()

    def _read_config(self):
        with open(self.config_path, 'r') as f:
            try:
                self.config = yaml.load(f.read())
            except:
                raise ConfigParsingError

    def _scrape_plugins(self):
        plugins = {}
        root_plugin_path = os.path.join(self.base_path, 'plugins')
        plugin_paths = [x[0] for x in os.walk(root_plugin_path)]
        for plugin in self.config['enabled_plugins']:
            loaded_plugin = None
            for path in plugin_paths:
                if os.path.basename(path) == plugin:
                    files = os.listdir(path)
                    for pfile in files:
                        if str(pfile) == 'plugin.py':
                            spec = importlib.util.spec_from_file_location(
                                "module.name",
                                os.path.join(root_plugin_path, path, pfile)
                                )
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            plugins[plugin] = module.SlackBotPlugin
                            loaded_plugin = True
            if not loaded_plugin:
                raise InvalidPlugin
        return plugins

    def _register_plugins(self, plugins):
        for key, value in plugins.items():
            self.registered_plugins[key] = {}
            plugin = value(client=self)
            try:
                for item in plugin.hooks:
                    if item not in self.registered_hooks:
                        self.registered_hooks.append(item)
            except AttributeError:
                pass
            self.registered_plugins[key] = plugin
            try:
                for item in plugin.trigger_phrases:
                    self.trigger_phrases.append(item)
                    self.trigger_plugins[key] = plugin
            except AttributeError:
                pass
            try:
                for item in plugin.help_pages:
                    for command, chelp in item.items():
                        self.help_pages.append(
                            {command: chelp}
                        )
            except AttributeError:
                pass
            sys.stdout.write(
                    "%sRegistered plugin: %s\n%s" % (
                        colors.OKGREEN,
                        key,
                        colors.RESET
                    )
                )
            sys.stdout.flush()

    def _get_users(self):
        api_call = self.client.api_call("users.list")
        if api_call.get('ok'):
            return api_call.get('members')

    def _get_my_id(self):
        for user in self.users:
            if 'name' in user and user.get('name') == self.name:
                return user.get('id')

    def _shutdown(self):
        self.running = False

    def _restart(self):
        self.running = False
        sleep(5)
        self.__bootstrap()

    def get_help_page(self, command):
        for page in self.help_pages:
            for key, value in page.items():
                if key == command:
                    return value
        else:
            return None

    def start_bot(self):
        READ_WEBSOCKET_DELAY = 1
        while self.running:
            try:
                exc_info = sys.exc_info()
                chan, user, msg, cmd, phrase = self.parse_slack_output(
                        self.client.rtm_read()
                        )
                if chan:
                    if msg and cmd:
                        self.handle_plugins(chan, user, msg)
                    elif cmd:
                        msg = "What?! Use '%slist' if you are confused." % (
                                    self.config['command_trigger']
                                )
                        self.send_channel_message(chan, msg)
                    elif phrase:
                        self.handle_trigger_plugins(chan, user, msg)
                    else:
                        pass
                del exc_info
                sleep(READ_WEBSOCKET_DELAY)
            except KeyboardInterrupt:
                sys.stdout.write("Shutting down...\n")
                sys.stdout.flush()
                self.running = False
            except Exception as err:
                traceback.print_tb(err.__traceback__)
                traceback.print_exception(*exc_info)
                del exc_info
                sys.stdout.write("Lost pipe...Reconnecting...")
                sys.stdout.flush()
                sleep(3)
                self._restart()

    def sanitize_handle(self, handle):
        fixed = handle
        for char in ['@', '<', '>']:
            fixed = fixed.replace(char, '')
        return fixed

    def get_user_profile(self, user_id):
        found = None
        for user in self.users:
            try:
                if user['id'].upper() == user_id.upper():
                    found = user
                    break
            except KeyError:
                pass
        return found

    def send_channel_message(self, channel, message, attachments=[],
                             action=False):
        if not action:
            call = 'chat.postMessage'
            response = self.client.api_call(
                call,
                channel=channel,
                text=message,
                attachments=attachments,
                as_user=True
            )
        else:
            call = 'chat.meMessage'
            response = self.client.api_call(
                call,
                channel=channel,
                text=message
                )
        if not response.get('ok'):
            sys.stdout.write(str(response))
            sys.stdout.flush()

    def send_channel_file(self, channel, title, filetype, content):
        api_call = self.client.api_call(
                "files.upload",
                channels=channel,
                title=title,
                filetype=filetype,
                content=content
                )
        if api_call.get('ok'):
            return api_call.get('file')

    def handle_trigger_plugins(self, channel, user, command):
        sys.stdout.write(
                "<%s/%s>: %s\n" % (
                    channel,
                    user['display_name'],
                    command)
                )
        sys.stdout.flush()
        sys.stdout.write(self.registered_plugins['console'].prompt)
        sys.stdout.flush()
        words = command.split(' ')
        for key, plugin in self.trigger_plugins.items():
            Thread(
                    target=self.call_trigger_plugin,
                    args=[plugin, channel, user, words]
                    ).start()

    def handle_plugins(self, channel, user, command):
        sys.stdout.write(
                "<%s/%s>: %s\n" % (
                    channel,
                    user['display_name'],
                    command)
                )
        sys.stdout.flush()
        sys.stdout.write(self.registered_plugins['console'].prompt)
        sys.stdout.flush()
        words = command.split(' ')
        for key, plugin in self.registered_plugins.items():
            Thread(
                    target=self.call_plugin,
                    args=[plugin, channel, user, words]
                    ).start()

    def register_loop(self, function, args=[], interval=10):
        Thread(
            target=self.run_plugin_loop,
            args=[function, interval, args]
        ).start()

    def run_plugin_loop(self, function, interval, args=[]):
        while self.running:
            sleep(interval)
            if len(args) > 0:
                function(*args)
            else:
                function()
            sleep(interval)

    def call_plugin(self, plugin, channel, user, words):
        try:
            my_exc = sys.exc_info()
            response = None
            response = plugin._on_recv(channel, user, words)
        except Exception as err:
            msg = "An error has occured and been logged accordingly."
            traceback.print_tb(err.__traceback__)
            traceback.print_exception(*my_exc)
            del my_exc
            self.send_channel_message(channel, msg)
        if response:
            if isinstance(response, str):
                self.send_channel_message(channel, response)
            elif isinstance(response, list):
                for item in response:
                    self.send_channel_message(channel, item)
            else:
                raise InvalidResponseFromPlugin
                del my_exc
            del my_exc

    def call_trigger_plugin(self, plugin, channel, user, words):
        response = plugin._on_trigger(channel, user, words)
        if response:
            if isinstance(response, str):
                self.send_channel_message(channel, response)
            elif isinstance(response, list):
                for item in response:
                    self.send_channel_message(channel, item)
            else:
                raise InvalidResponseFromPlugin

    def parse_slack_output(self, slack_rtm_output):
        output_list = slack_rtm_output
        if output_list and len(output_list) > 0:
            cmd_trigger = False
            phrase_trigger = False
            msg = ''
            for output in output_list:
                if output and 'text' in output:
                    text = output['text']
                    try:
                        seed = text.split()[0]
                    except IndexError:
                        seed = None
                    if seed and seed.startswith(
                            self.config['command_trigger']):
                        formatted = seed.replace(
                                self.config['command_trigger'], ''
                                ).lower()
                        if formatted in self.registered_hooks:
                            cmd_trigger = True
                            msg = text.strip().lower()[1:]
                        else:
                            pass
                    elif self.at_bot in text or self.display_name in text:
                        if output.get('user') and output.get('user') == self.bot_id:
                            pass
                        else:
                            cmd_trigger = True
                            try:
                                msg = text.split(
                                    self.at_bot
                                    )[1].strip().lower()
                            except:
                                msg = text
                    else:
                        msg = text.strip().lower()
                        for item in self.trigger_phrases:
                            if item.lower() in msg.lower():
                                phrase_trigger = True
                    if output.get('user'):
                        return \
                            output['channel'], \
                            self.get_user_profile(output['user'])['profile'], \
                            msg, \
                            cmd_trigger, \
                            phrase_trigger
        return None, None, None, None, None
