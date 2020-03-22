#!/usr/bin/python3

import os
import sys
import time
import threading
import importlib.util

from slack import RTMClient

from ..logging import SlackBotLogger as logger
from ..config import SlackBotConfig as config
from ..db import DatabaseSession
from .pluginmanager import PluginManager
from .context import ContextManager
from .exceptions import ConfigParsingError, InvalidCredentials, InvalidPlugin, \
        InvalidResponseFromPlugin, MissingBotName, MissingSlackToken


class SlackBot(object):

    def __init__(self):
        logger.info("Starting up Slack Bot", format_opts=["header"])
        basedir = os.path.dirname(os.path.realpath(__file__))
        self.base_path = os.path.join(basedir, '..', '..')
        self.ready_event = threading.Event()
        self.stop_event = threading.Event()
        self.__bootstrap()

    def __bootstrap(self):
        logger.info("Loading configuration...")
        self.__verify_config()
        logger.debug("Initializing kv store session")
        self.db = DatabaseSession()
        logger.debug("Initializing context manager")
        self.contexts = ContextManager(self)
        logger.info("Loading Plugins...")
        self.plugins = PluginManager(self, os.path.join(self.base_path, 'plugins'))

    def __verify_config(self):
        self.name = config.get('bot_name')
        if not self.name:
            raise MissingBotName
        logger.debug(f"Using bot name: {self.name}")
        slack_token = config.get('slack_token')
        if not slack_token:
            raise MissingSlackToken
        logger.debug("Retieved slack token from configuration")
        self.admins = config.get('admins') or []
        logger.debug(f"Configured admins: {self.admins}")

    def _get_users(self):
        api_call = self.client.api_call("users.list")
        if api_call.get('ok'):
            return api_call.get('members')

    def _get_my_id(self):
        for user in self.users:
            if 'name' in user and user.get('name') == self.name:
                return user.get('id')

    def _wait(self, interval):
        self.stop_event.wait(interval)

    def _handle_plugin_response(self, channel, response):
        if isinstance(response, str):
            self.send_channel_message(channel, response)
        elif isinstance(response, list):
            for item in response:
                self.send_channel_message(channel, item)
        else:
            logger.info(f"Invalid response from plugin: {response}")

    def _is_not_message(self, output):
        if output.get('text'):
            if output['text'].strip() != '':
                return False
        return True

    def _is_self_message(self, output):
        return output.get('user') and output.get('user') == self.bot_id

    def is_mention(self, text):
        return self.at_bot in text

    def shutdown(self):
        logger.info("Received shutdown signal...")
        self.stop_event.set()
        self.rtm_client.stop()

    def restart(self):
        self.shutdown()
        time.sleep(5)
        self.__bootstrap()
        self.start()

    def ready(self):
        return self.ready_event.is_set()

    def running(self):
        return not self.stop_event.is_set()

    def start(self):
        try:
            self.rtm_client = RTMClient(token=config.get('slack_token'))
            self.rtm_client.start()
        except KeyboardInterrupt:
            self.shutdown()

    def get_help_page(self, command):
        return self.plugins.get_help_page(command)

    def handle_hello(self, payload):
        logger.debug("Received 'hello' from slack rtm api")
        logger.debug("Setting slack web/rtm clients")
        self.client = payload.get('web_client')
        logger.debug("Retrieving user list")
        self.users = self._get_users()
        logger.debug("Gathering information about myself")
        self.bot_id = self._get_my_id()
        self.display_name = self.get_user_profile(self.bot_id)['name']
        self.at_bot = "<@" + self.bot_id + ">"
        self.ready_event.set()
        logger.info("Initialization Complete!", format_opts=["green"])

    def handle_message(self, payload):
        logger.debug(f"Handling slack message payload: {payload}")
        output = payload.get('data')
        if self._is_not_message(output) or self._is_self_message(output):
            return
        channel = output.get('channel')
        if not channel:
            return
        try:
            logger.debug("Looking up source user of event")
            user = self.get_user_profile(output['user'])
            logger.debug(f"User: {user}")
        except Exception as err:
            log.error(f"Failed to fetch user for event: {output}", err, sys.exc_info())
            return
        text = output['text']
        try:
            logger.info(f"<{channel}/{user['profile']['display_name']}>: {text}")
            cmd, words = self.plugins.get_cmd(text)
            if cmd:
                res = self.plugins.serve_cmd(channel, user, cmd, words)
                if res:
                    self._handle_plugin_response(channel, res)
                return
            words = text.split()
            ctx = self.contexts.get_context(channel, user['id'])
            if ctx:
                if ctx.is_finished() or ctx.is_expired():
                    return
                with self.contexts.lock:
                    res = self.plugins.serve_context(channel, user, ctx, words)
                    if res:
                        self._handle_plugin_response(channel, res)
                    ctx.messages.append(words)
                    return
            trigger = self.plugins.get_trigger(text)
            if trigger:
                res = self.plugins.serve_trigger(channel, user, trigger, words)
                if res:
                    self._handle_plugin_response(channel, res)
                return
            if self.is_mention(text):
                text.replace(self.at_bot, "")
                res = self.plugins.serve_mention(channel, user, text.split())
                if res:
                    self._handle_plugin_response(channel, res)
                    return
            logger.debug("No plugins matched the event")
        except Exception as err:
            logger.error("Failed processing message", err, sys.exc_info())
            self._handle_plugin_response(channel, "An error has occurred and been logged accordingly")

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
        logger.debug(
            f"""Sending channel message:
            channel: {channel}
            message: {message}
            action: {action}
            attachments: {attachments}
            """
        )
        if not action:
            response = self.client.chat_postMessage(
                channel=channel,
                text=message,
                attachments=attachments,
                as_user=True
            )
        else:
            response = self.client.chat_meMessage(
                channel=channel,
                text=message
            )
        if not response.get('ok'):
            logger.info(str(response))

    def send_channel_file(self, channel, title, filetype, content):
        logger.debug(
            f"""Uploading file to channel
            channel: {channel}
            filename: {title}
            filetype: {filetype}
            """
        )
        api_call = self.client.files_upload(
            channels=channel,
            title=title,
            filetype=filetype,
            content=content
        )
        if api_call.get('ok'):
            return api_call.get('file')

    def register_loop(self, function, args=[], interval=10):
        logger.debug(
            f"""Registering plugin loop
            Function: {function}
            args: {args}
            interval: {interval}
            """
        )
        threading.Thread(
            target=self.run_plugin_loop,
            args=[function, interval, args],
            daemon=True
        ).start()

    def run_plugin_loop(self, function, interval, args=[]):
        self._wait(interval)
        while self.running():
            try:
                if len(args) > 0:
                    logger.debug(f"Firing {function} with args: {args}")
                    function(*args)
                else:
                    logger.debug(f"Firing {function}")
                    function()
                self._wait(interval)
            except Exception as err:
                logger.error("Exception while running plugin loop", err, sys.exc_info())
                self._wait(interval)
