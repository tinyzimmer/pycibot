#!/usr/bin/python3

from lib.builtins import BasePlugin
import requests
import json


class SlackBotPlugin(BasePlugin):

    hooks = ['google']
    help_pages = [{'google': 'google <query> - do a google search'}]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.api_key = self.client.config['google_api_key']
        self.engine_id = self.client.config['search_engine_id']
        self.base_url = 'https://www.googleapis.com/customsearch/v1'

    def _generate_attachment(self, item):
        attachment = {
                "fallback": item['title'],
                "title": item['title'],
                "title_link": item['link'],
                "text": item['snippet']
                }
        return attachment

    def query(self, query):
        search_url = '%s?q=%s&cx=%s&key=%s' % (
                self.base_url,
                query,
                self.engine_id,
                self.api_key
                )
        response = requests.get(search_url)
        lucky = json.loads(response.content)['items'][0]
        attachment = self._generate_attachment(lucky)
        return attachment

    def on_recv(self, channel, user, words):
        if words[0] == 'google':
            response = self.query(' '.join(words[1:]))
            if response:
                self.client.send_channel_message(
                    channel,
                    '',
                    [response]
                )
