#!/usr/bin/python3

from lib.builtins import BasePlugin
from lib.config import SlackBotConfig as config
from lib.logging import SlackBotLogger as logger
from urllib.parse import urlsplit
import feedparser
import re


class SlackBotPlugin(BasePlugin):

    def setUp(self):
        self.subreddits = config.get('subreddits')
        self.active_channels = config.get('channels')
        self.db = self.client.db
        self.feeds = {}
        self.started = False
        for sub in self.subreddits:
            self.feeds[sub] = 'https://www.reddit.com/r/%s/new/.rss' % sub
        self.client.register_loop(self.check_feeds, interval=30)

    def _generate_attachment(self, item, link):
        base_url = "{0.scheme}://{0.netloc}/".format(urlsplit(link))
        src = base_url.split('/')[-2].split('.')[0]
        if src and src != 'www':
            title = '%s: %s' % (src, item['title'])
        elif src and src == 'www':
            src = base_url.split('/')[-2].split('.')[1]
            title = '%s: %s' % (src, item['title'])
        else:
            title = item['title']
        attachment = {
                "fallback": title,
                "title": title,
                "title_link": link,
                "text": ''
                }
        return attachment

    def _parse_item(self, item):
        urls = re.findall('(https?://[^\s]+?[^>])">', item['summary'])
        link = None
        for url in urls:
            if 'reddit' not in url:
                link = url
        if link:
            return self._generate_attachment(item, link)
        else:
            return None

    def check_feeds(self):
        if self.started:
            for sub, feed in self.feeds.items():
                response = feedparser.parse(feed)
                try:
                    last = response['items'][0]
                except IndexError:
                    return
                announced = self.db.get_value(sub)
                if not announced or last['title'] not in announced:
                    if not announced:
                        announced = [last['title']]
                    else:
                        if len(announced) >= 10:
                            del announced[0]
                        announced.append(last['title'])
                    response = self._parse_item(last)
                    if response:
                        for channel in self.active_channels:
                            self.client.send_channel_message(
                                channel,
                                '',
                                [response]
                            )
                    self.db.store_value(sub, announced)
        else:
            self.started = True
            for sub, feed in self.feeds.items():
                announced = self.db.get_value(sub)
                response = feedparser.parse(feed)
                try:
                    last = response['items'][0]
                    if announced:
                        if len(announced) >= 10:
                            del announced[0]
                        if last['title'] not in announced:
                            announced.append(last['title'])
                    else:
                        announced = [last['title']]
                    self.db.store_value(sub, announced)
                except IndexError:
                    return

    def on_recv(self, channel, user, cmd, words):
        pass
