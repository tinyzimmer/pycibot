#!/usr/bin/python3

from chatterbot import ChatBot
from lib.builtins import BasePlugin
import sys


class SlackBotPlugin(BasePlugin):

    hooks = []
    help_pages = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.chatbot = ChatBot(
            'chatterbot',
            trainer='chatterbot.trainers.ChatterBotCorpusTrainer'
        )
        self.initial_training()
        self.hooks = []

    def initial_training(self):
        self.chatbot.train(
            "chatterbot.corpus.english"
        )

    def on_recv(self, channel, user, words):
        message = ' '.join(words)
        no_action = False
        if 'show me your source' in message:
            no_action = True
        else:
            for phrase in self.client.trigger_phrases:
                if phrase.lower() in message.lower():
                    no_action = True
        if words[0] not in self.client.registered_hooks \
                and not no_action:
            if 'joined the group' in message or \
                    'joined the channel' in message:
                return "Hello there!"
            if not message.startswith('uploaded a file:'):
                sys.stdout.write("Receiving response from chatterbot\n")
                response = self.chatbot.get_response(message)
                return str(response)
