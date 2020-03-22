#!/usr/bin/env python3

from .builtins import BuiltInHelp, BuiltInReload, BuiltInRestart, \
                      BuiltInShutdown, BuiltInGreet, BuiltInSource, BasePlugin


BUILTIN_PLUGINS = {
    'help': BuiltInHelp,
    'reload': BuiltInReload,
    'restart': BuiltInRestart,
    'shutdown': BuiltInShutdown,
    'greet': BuiltInGreet,
    'source': BuiltInSource,
}
