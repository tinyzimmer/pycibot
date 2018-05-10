#!/usr/bin/python3

from lib.builtins import BasePlugin
from urllib.parse import urlsplit
import feedparser
import re


class AnnouncedArticles(object):

    def __init__(self):
        self.records = {}

    def emit(self, sub, item):
        try:
            if len(self.records[sub]) >= 10:
                del self.records[sub][0]
            self.records[sub].append(item)
        except KeyError:
            self.records[sub] = [item]


class SlackBotPlugin(BasePlugin):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.subreddits = self.client.config['subreddits']
        self.active_channels = self.client.config['reddit_active_channels']
        self.feeds = {}
        self.announced = AnnouncedArticles()
        self.started = False
        for sub in self.subreddits:
            self.feeds[sub] = 'https://www.reddit.com/r/%s/new/.rss' % sub
            self.announced.emit(sub, None)
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
                if last['title'] not in self.announced.records[sub]:
                    self.announced.emit(sub, last['title'])
                    response = self._parse_item(last)
                    if response:
                        for channel in self.active_channels:
                            self.client.send_channel_message(
                                channel,
                                '',
                                [response]
                            )
        else:
            self.started = True
            for sub, feed in self.feeds.items():
                response = feedparser.parse(feed)
                try:
                    last = response['items'][0]
                    self.announced.emit(sub, last['title'])
                except IndexError:
                    return

    def on_recv(self, channel, user, words):
        pass
