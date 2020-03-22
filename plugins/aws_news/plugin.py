#!/usr/bin/python3

from lib.builtins import BasePlugin
from lib.config import SlackBotConfig as config
import feedparser


class SlackBotPlugin(BasePlugin):

    def setUp(self):
        self.active_channels = config.get('channels')
        self.feed = 'https://aws.amazon.com/new/feed'
        self.announced = []
        self.started = False
        self.client.register_loop(self.check_feeds, interval=30)

    def _generate_attachment(self, item):
        attachment = {
                "fallback": item['title'],
                "title": item['title'],
                "title_link": item['link'],
                "text": item['summary']
                }
        return attachment

    def check_feeds(self):
        if self.started:
            response = feedparser.parse(self.feed)
            try:
                last = response['items'][0]
            except IndexError:
                return
            if last not in self.announced:
                self.announced.append(last)
                response = self._generate_attachment(last)
                if response:
                    for channel in self.active_channels:
                        self.client.send_channel_message(
                            channel,
                            '',
                            [response]
                        )
        else:
            self.started = True
            response = feedparser.parse(self.feed)
            last = response['items'][0]
            self.announced.append(last)

    def on_recv(self, channel, user, cmd, words):
        pass
