#!/usr/bin/python3

import os
import nltk
from pathlib import Path
from distutils.dir_util import copy_tree
from chatterbot import ChatBot
from chatterbot.trainers import ChatterBotCorpusTrainer
from chatterbot.conversation import Statement

from lib.builtins import BasePlugin
from lib.config import SlackBotConfig as config
from lib.logging import SlackBotLogger as logger


class SlackBotPlugin(BasePlugin):

    hooks = []
    help_pages = []

    def setUp(self):
        data_dir = config.get('data_dir')
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)
            db_path = f"sqlite:///{os.path.join(data_dir, 'chatdb.sqlite3')}"
            nltk_dir = os.path.join(data_dir, "nltk_data")
            nltk.data.path.insert(0, nltk_dir)
            for pkg in ["wordnet", "stopwords", "averaged_perceptron_tagger"]:
                nltk.download(pkg, download_dir=nltk_dir)
            copy_tree(nltk_dir, os.path.join(str(Path.home()), "nltk_data"))
        else:
            db_path = f"sqlite:///db.sqlite3"
        self.contexts = self.client.contexts
        self.chatbot = ChatBot(
            'chatterbot',
            database_uri=db_path,
            logic_adapters=[
                'chatterbot.logic.BestMatch',
                'chatterbot.logic.MathematicalEvaluation',
                #'chatterbot.logic.TimeLogicAdapter'
            ]
        )
        self.initial_training()

    def initial_training(self):
        self.trainer = ChatterBotCorpusTrainer(self.chatbot)
        self.trainer.train(
            "chatterbot.corpus.english"
        )

    def on_context(self, channel, user, ctx, words):
        if ctx.get('last_statement'):
            inp = Statement(
                text=' '.join(words),
                in_response_to=str(ctx.get('last_statement')),
            )
        else:
            inp = Statement(text=' '.join(words))
        response = self.chatbot.get_response(inp)
        ctx.set('last_statement', response)
        return str(response)


    def on_recv(self, channel, user, cmd, words):
        message = ' '.join(words)
        if 'joined the group' in message or \
                'joined the channel' in message:
            return "Hello there!"
        if message.startswith('uploaded a file:'):
            return
        if 'lets chat' in message.replace("'", "").lower():
            ctx = self.contexts.new_context(channel, user['id'], messages=[words], timeout=120)
            return "Okay, I'm ready!"
        logger.info("Receiving response from chatterbot")
        response = self.chatbot.get_response(message)
        return str(response)
