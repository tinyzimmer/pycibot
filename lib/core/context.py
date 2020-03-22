#!/usr/bin/env python3

import inspect
import threading
from datetime import datetime, timedelta

from ..logging import SlackBotLogger as logger


def get_caller():
    caller = inspect.stack()[2][1]
    return caller.split("/")[-2]


class Context(object):

    def __init__(self, plugin, channel, user_id, timeout=60, messages=[], timeout_message=None, timeout_use_action=False):
        self.plugin = plugin
        self.channel = channel
        self.user_id = user_id
        self.start = datetime.now()
        self.end = self.start + timedelta(seconds=timeout)
        self.messages = messages
        self.timeout_message = timeout_message
        self.timeout_use_action = timeout_use_action
        self.finished = threading.Event()
        self.values = {}

    def _cleanup(self, client):
        if self.timeout_message:
            args = {
                "channel": self.channel,
                "message": self.timeout_message,
            }
            if self.timeout_use_action is True:
                args["action"] == True
            client.send_channel_message(**args)

    def is_expired(self):
        return self.end <= datetime.now()

    def is_finished(self):
        return self.finished.is_set()

    def get(self, key):
        return self.values.get(key)

    def get_all(self):
        return self.values

    def set(self, key, value):
        self.values[key] = value

    def set_timeout_message(self, msg, action=False):
        self.timeout_message = msg
        self.timeout_use_action = action

    def finish(self):
        self.finished.set()


class ContextManager(object):

    def __init__(self, client):
        self.client = client
        self.contexts = {}
        self.lock = threading.Lock()
        threading.Thread(
            target=self._run_context_gc,
            daemon=True
        ).start()

    def _chan_ctx_for_user(self, channel, user_id):
        if not self.contexts.get(user_id):
            return None
        for x in self.contexts[user_id]:
            if channel == x.channel:
                return x
        return None

    def _run_context_gc(self):
        while not self.client.ready():
            self.client._wait(3)
        logger.debug("Starting context garbage collection loop")
        while self.client.running():
            expired = []
            finished = []
            for user, ctxs in self.contexts.items():
                for ctx in ctxs:
                    if ctx.is_finished():
                        finished.append(ctx)
                    elif ctx.is_expired():
                        expired.append(ctx)
            for ctx in expired:
                logger.debug(f"Context has expired: {vars(ctx)}")
                ctx._cleanup(self.client)
                self.finish_context(ctx)
            for ctx in finished:
                logger.debug(f"Context is finished: {vars(ctx)}")
                self.finish_context(ctx)
            self.client._wait(5)

    def new_context(self, channel, user_id, timeout=60, messages=[], timeout_message=None, timeout_use_action=False):
        with self.lock:
            if not self.contexts.get(user_id):
                self.contexts[user_id] = []
            ctx = Context(
                get_caller(),
                channel,
                user_id,
                timeout=timeout,
                messages=messages,
                timeout_message= timeout_message,
                timeout_use_action=timeout_use_action
            )
            self.contexts[user_id].append(ctx)
            return ctx

    def get_context(self, channel, user_id):
        return self._chan_ctx_for_user(channel, user_id)

    def finish_context(self, ctx):
        with self.lock:
            new_ctxs = [x for x in self.contexts[ctx.user_id] if x.channel != ctx.channel]
            if len(new_ctxs) == 0:
                del self.contexts[ctx.user_id]
            else:
                self.contexts[ctx.user_id] = new_ctxs
