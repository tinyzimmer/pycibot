#!/usr/bin/env python3

import re

from lib.builtins import BasePlugin
from lib.logging import SlackBotLogger as logger

from nltk.corpus import stopwords


KEYWORDS = [
    "pod", "pods",
    "deployment", "deployments",
    "service", "services",
    "namespace", "namespaces"
]
trigger_regex_string = r"pods?|deployments?|services?"
trigger_regex = re.compile(trigger_regex_string)


class SlackBotPlugin(BasePlugin):

    hooks = []
    trigger_regexes = [trigger_regex_string]

    def setUp(self):
        self.contexts = self.client.contexts

    def get_action(self, words):
        if "get" in words:
            return "get", [word for word in words if word != "get"]
        elif "delete" in words:
            return "delete", [word for word in words if word != "delete"]
        elif "describe" in words:
            return "describe", [word for word in words if word != "describe"]
        return None, None

    def set_context_args(self, ctx, args):
        for idx, token in enumerate(args):
            if token in KEYWORDS:
                if idx == 0:
                    val = args[1] if args[1] not in KEYWORDS else None
                    if val:
                        ctx.set(token, val)
                    continue
                if idx == len(args)-1:
                    val = args[-2] if args[-2] not in KEYWORDS else None
                    if val:
                        ctx.set(token, val)
                    break
                val = args[idx-1] if args[idx-1] not in KEYWORDS else None
                if val:
                    ctx.set(token, val)
                    continue
                val = args[idx+1] if args[idx+1] not in KEYWORDS else None
                if val:
                    ctx.set(token, val)
        return ctx

    def strip_stop_words(self, words):
        stwords = stopwords.words("english")
        trimmed = [word for word in words if word not in stwords and word != self.client.at_bot]
        return trimmed

    def on_trigger(self, channel, user, words):
        if not self.client.is_mention(words):
            return
        trimmed = self.strip_stop_words(words)
        action, args = self.get_action(trimmed)
        if not action:
            return "Sorry, I didn't understand what you wanted to do"

        if len(args) == 1:
            return "Sorry, that's not enough to go on..."

        ctx = self.contexts.new_context(channel, user['id'], messages=[words])
        ctx.set("action", action)
        ctx.set("resource", trigger_regex.search(' '.join(args)).group(0))
        ctx = self.set_context_args(ctx, args)
        if not ctx.get("namespace"):
            ctx.set("question", "namespace")
            return "Which namespace am I looking in?"
        logger.info(ctx.values)

    def on_context(self, channel, user, ctx, words):
        trimmed = self.strip_stop_words(words)
        if ctx.get("question") and ctx.get("question") == "namespace":
            if len(trimmed) != 1:
                return "Sorry I didn't catch that..."
            ctx.set("namespace", trimmed[0])
            ctx.set("question", None)
        logger.info(ctx.values)
