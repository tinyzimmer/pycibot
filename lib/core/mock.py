#!/usr/bin/env python3

import sys
import time

from .bot import SlackBot
from ..logging import SlackBotLogger as logger
from ..logging import Colors

try:
    import readline
except:
    pass


class MockClient(object):

    def __getattr__(self, name):
        def method(*args, **kwargs):
            cmdlinestr = ', '.join(args)
            for k, v in kwargs.items():
                cmdlinestr += f"{k}='{v}', "
            if cmdlinestr.endswith(", "):
                cmdlinestr = cmdlinestr[:-2]
            logger.debug(
                f"Slack API Call: {name}({cmdlinestr})",
                format_opts=["bold"]
            )
            print("---")
            print(f"\N{SPEECH BALLOON} {Colors.BOLD}mockbot: {Colors.WARNING}{kwargs.get('text') or '<no response>'}{Colors.RESET}")
            return {'ok': True, 'file': 'fake_file'}
        return method


class MockBot(SlackBot):

    def start(self):
        logger.debug("Setting up mock api client")
        self.client = MockClient()
        logger.debug("Populating mock users")
        self.users = [
            {
                "id": "console",
                "name": "console",
                "real_name": "console",
                "profile": {"display_name": "console"}
            },
            {
                "id": "mockbot",
                "name": "mockbot",
                "real_name": "mockbot",
                "profile": {"display_name": "mockbot"}
            }
        ]
        logger.debug("Setting self attributes")
        self.bot_id = "mockbot"
        self.at_bot = "<@" + self.bot_id + ">"
        self.ready_event.set()
        logger.info(
            "Mockbot Initialization Complete! Launching console.",
            format_opts=["green"]
        )
        time.sleep(3)
        self.console()

    def register_loop(self, function, args=[], interval=10):
        logger.info(
            f"""Would have registered loop, but running in mock mode:
            Function: {function}
            args: {args}
            interval: {interval}
            """
        )

    def help(self):
        print("#########################################################################################################################")
        print("## You are in mockbot mode. You can interact with the bot as if you were private messaging one another.                ##")
        print("## All Slack API calls will be mocked and logged to the console. To simulate an at-mention to the bot, use '@mockbot'. ##")
        print("## Set logging.debug to 'true' in your config for more verbosity.                                                      ##")
        print("## Up/Down for history. ^C to cancel an event or clear the input. ^D to quit. Type 'help' to reprint this message.     ##")
        print("#########################################################################################################################")

    def console(self):

        self.help()
        waiting = False
        prompt = f"{Colors.GREEN}{Colors.BOLD}[console@mock{Colors.RESET} {Colors.BOLD}pycibot{Colors.GREEN}]{Colors.RESET} \N{LEFT SPEECH BUBBLE} "

        @logger.on_log
        def reprompt(val):
            if "context" in val.lower() and waiting is False:
                sys.stdout.write(prompt)
                sys.stdout.flush()

        while True:
            waiting = False

            try:
                inp = input(prompt)
                if inp == "":
                    continue
                elif inp == "help":
                    self.help()
                    continue

                waiting = True
                self.handle_message({
                    "data": {
                        "channel": "mock",
                        "user": "console",
                        "text": inp.replace("@mockbot", self.at_bot)
                    }
                })
            except KeyboardInterrupt:
                print("^C")
                continue
            except EOFError:
                print()
                logger.info("Shutting down mock console...")
                break
