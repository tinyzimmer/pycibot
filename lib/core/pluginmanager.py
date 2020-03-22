#!/usr/bin/env python3

import os
import re
import importlib.util

from ..builtins import BUILTIN_PLUGINS
from ..logging import SlackBotLogger as logger
from ..config import SlackBotConfig as config


class HookManager(object):

    def __init__(self):
        self.registered_plugins = {}
        self.registered_hooks = {}
        self.registered_triggers = {}

    def register_hook(self, plugin_name, hook):
        if self.registered_hooks.get(plugin_name):
            self.registered_hooks[plugin_name].append(hook)
        else:
            self.registered_hooks[plugin_name] = [hook]

    def register_trigger(self, plugin_name, trigger):
        regex = re.compile(trigger, re.I)
        if self.registered_triggers.get(plugin_name):
            self.registered_triggers[plugin_name].append(regex)
        else:
            self.registered_triggers[plugin_name] = [regex]

    def register_plugin(self, name, plugin):
        self.registered_plugins[name] = plugin

    def get_hook_by_name(self, name):
        return self.registered_plugins.get(name)

    def get_cmd_hook(self, cmd):
        for k, v in self.registered_hooks.items():
            if cmd in v:
                return self.registered_plugins[k]
        return None

    def get_trigger_hook(self, trigger):
        for k, v in self.registered_triggers.items():
            if trigger in v:
                return self.registered_plugins[k]
        return None

    def get_trigger_phrase(self, msg):
        for k, v in self.registered_triggers.items():
            for regex in v:
                if regex.search(msg):
                    return regex
        return None

    def get_all_hooks(self):
        hooks = []
        for k, v in self.registered_hooks.items():
            for hook in v:
                hooks.append(hook)
        return hooks


class PluginManager(object):

    def __init__(self, client, plugin_dir):
        self.hook_manager = HookManager()
        self.trigger_plugins = {}
        self.trigger_phrases = []
        self.help_pages = []
        self._load_builtin_plugins(client)
        plugins = self._scrape_plugins(plugin_dir)
        for name, plugin in plugins.items():
            loaded = plugin(client=client)
            loaded._setUp()
            self._register_plugin(name, loaded)

    def _load_builtin_plugins(self, client):
        for key, plugin in BUILTIN_PLUGINS.items():
            loaded = plugin(client=client)
            self._register_plugin(key, loaded)

    def _scrape_plugins(self, root_plugin_path):
        plugins = {}
        plugin_paths = [x[0] for x in os.walk(root_plugin_path)]
        enabled_plugins = config.get('enabled_plugins') or []
        for plugin in enabled_plugins:
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
                raise Exception(f"Plugin {plugin} is invalid")
        return plugins

    def _register_plugin(self, name, loaded):
        self.hook_manager.register_plugin(name, loaded)
        if hasattr(loaded, 'hooks') and isinstance(loaded.hooks, list):
            for item in loaded.hooks:
                self.hook_manager.register_hook(name, item)
        if hasattr(loaded, 'help_pages') and isinstance(loaded.help_pages, list):
            for item in loaded.help_pages:
                for command, chelp in item.items():
                    self.help_pages.append({command: chelp})
        if hasattr(loaded, 'trigger_regexes') and isinstance(loaded.trigger_regexes, list):
            for item in loaded.trigger_regexes:
                self.hook_manager.register_trigger(name, item)
        logger.info(f"Registered plugin: {name}", format_opts=["green"])

    def get_help_page(self, cmd):
        for item in self.help_pages:
            for k, v in item.items():
                if k.lower() == cmd.lower():
                    return v

    def get_all_hooks(self):
        return self.hook_manager.get_all_hooks()

    def get_cmd(self, msg):
        cmd_trigger = config.get('command_trigger')
        if cmd_trigger:
            seed = msg.split()[0]
            if seed.startswith(cmd_trigger):
                if self.hook_manager.get_cmd_hook(seed.lower()[1:]):
                    return seed.lower()[1:], msg.split()[1:]
        return None, None

    def get_trigger(self, msg):
        return self.hook_manager.get_trigger_phrase(msg)

    def serve_cmd(self, channel, user, cmd, words):
        logger.debug(
            f"""Serving command trigger
            channel: {channel}
            user: {user['profile']['display_name']}
            cmd: {cmd}
            args: {words}
            """
        )
        return self.hook_manager.get_cmd_hook(cmd)._on_recv(channel, user, cmd, words)

    def serve_trigger(self, channel, user, trigger, words):
        logger.debug(
            f"""Serving phrase trigger
            channel: {channel}
            user: {user['profile']['display_name']}
            trigger: {trigger}
            text: {' '.join(words)}
            """
        )
        return self.hook_manager.get_trigger_hook(trigger)._on_trigger(channel, user, words)

    def serve_context(self, channel, user, ctx, words):
        logger.debug(
            f"""Serving context
            channel: {channel}
            user: {user['profile']['display_name']}
            context: {vars(ctx)}
            """
        )
        return self.hook_manager.get_hook_by_name(ctx.plugin)._on_context(channel, user, ctx, words)

    def serve_mention(self, channel, user, words):
        chatterbot = self.hook_manager.get_hook_by_name('chatterbot')
        if chatterbot:
            return chatterbot._on_recv(channel, user, "", words)
        return None
