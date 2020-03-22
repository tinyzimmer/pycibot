#!/usr/bin/python3

import os
import sys
import argparse

from slack import RTMClient

from lib.core.bot import SlackBot
from lib.core.mock import MockBot
from lib.config import SlackBotConfig as conf
from lib.logging import SlackBotLogger as logger


conf.build(os.environ.get('SLACK_BOT_CONFIG') or "./config.yml")
logger.build(conf)


if len(sys.argv) > 1 and sys.argv[1] == "-m":
    bot = MockBot()
else:
    bot = SlackBot()


@RTMClient.run_on(event='hello')
def on_hello(**payload):
    bot.handle_hello(payload)


@RTMClient.run_on(event='message')
def on_message(**payload):
    bot.handle_message(payload)


@conf.run_on_change
def handle_config_change():
    logger.info("Restarting bot for configuration change")
    # global bot
    # bot.shutdown()
    # del bot
    # bot = SlackBot()
    # bot.start()


def run():
    try:
        bot.start()
    except KeyboardInterrupt:
        bot.shutdown()


if __name__ == '__main__':
    run()
