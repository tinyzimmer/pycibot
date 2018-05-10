#!/usr/bin/python3

from lib.builtins import BasePlugin
from plugins.google.plugin import SlackBotPlugin as GooglePlugin
import requests
import json
import os
import re


class SlackBotPlugin(BasePlugin):

    hooks = ['search', 'elk']
    help_pages = [{'search': 'search <confluence query>'}]
    trigger_phrases = [
            'how do i',
            'how do we',
            'where is the',
            'where are the',
            'what are the',
            'what is the',
            'are there',
            'is there',
            'trying to understand'
        ]
    basedir = os.path.dirname(os.path.realpath(__file__))
    stoplist_path = os.path.join(basedir, 'stoplist.txt')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            self.space = self.client.config['confluence_space']
        except KeyError:
            self.space = None
        try:
            self.fallback = bool(
                    self.client.config['confluence_google_fallback']
                )
        except Exception:
            self.fallback = False
        with open(self.stoplist_path, 'r') as f:
            self.stoplist = f.readlines()
        if self.fallback:
            self.google = GooglePlugin(**kwargs)

    def _trim_stoplist(self, words):
        new_list = []
        for word in words:
            if word.lower() not in self.stoplist:
                new_list.append(word)
        return new_list

    def on_trigger(self, channel, user, words):
        trigger = self.get_trigger(words)
        if trigger:
            message = ' '.join(words).lower()
            split = message.split(
                    trigger
                )[1].split()
            stripped = self._trim_stoplist(split)
            if len(stripped) > 3:
                params = stripped[:3]
            else:
                params = stripped
            attachment = self.get_query(params, cmd=False)
            if attachment:
                self.client.send_channel_message(
                    channel,
                    '',
                    [attachment]
                )

    def on_recv(self, channel, user, words):
        if words[0] == 'search':
            return self.received_search(channel, user, words)
        if words[0] == 'elk':
            return self.received_elk(channel, user, words)

    def received_elk(self, channel, user, words):
        result = self.run_query(['kibana', 'urls'])
        url = result['_links']['self']
        qurl = "%s?expand=body.storage" % url
        response = requests.get(qurl)
        data = json.loads(response.content)['body']['storage']['value']
        links = re.findall('(https?://[^\s]+?[^\.html]).html', data)
        returns = []
        sterm = 'elk-%s' % words[1]
        msg = ''
        index = 0
        envs = ['POC', 'DEV/SIT', 'UAT', 'PRD']
        for link in links:
            if sterm in link and link not in returns:
                msg += '*%s*: %s.html\n' % (envs[index], link)
                returns.append(link)
                index += 1
        return msg

    def received_search(self, channel, user, words):
            if len(words) < 2:
                return self.client.get_help_page('search')
            else:
                attachment = self.get_query(words[1:], cmd=True)
                if isinstance(attachment, str):
                    if self.fallback:
                        gquery = ' '.join(words[1:])
                        attachment = self.google.query(gquery)
                        msg = "Nothing in Confluence, but found this on google"
                        self.client.send_channel_message(
                                channel,
                                msg,
                                [attachment]
                            )
                    else:
                        return attachment
                else:
                    self.client.send_channel_message(
                        channel,
                        '',
                        [attachment]
                    )

    def get_query(self, words, cmd=True):
        if self.space:
            result = self.run_query(words, self.space)
        else:
            result = self.run_query(words)
        if not result and self.space:
            result = self.run_query(words)
            if not result and cmd:
                return "Sorry, I couldn't find anything on that."
            elif result:
                return self.form_attachment(result)
        elif not result and cmd:
            return "Sorry, I couldn't find anything on that."
        else:
            return self.form_attachment(result)

    def form_attachment(self, result):
        confluence_url = self.client.config['confluence_url']
        link = "%s/%s" % (confluence_url, result['_links']['webui'])
        name = "%s - %s" % (result['title'], link)
        attachment = {
                'fallback': name,
                'title': name,
                'title_link': link
            }
        return attachment

    def run_query(self, words, space=None):
        if space:
            query = self.form_query(words, space)
        else:
            query = self.form_query(words)
        confluence_url = self.client.config['confluence_url']
        qurl = "%s/rest/api/content/search?%s" % (
                confluence_url, query
            )
        response = requests.get(qurl)
        data = json.loads(response.content)
        try:
            result = data['results'][0]
            return result
        except (IndexError, KeyError):
            return None

    def form_query(self, params, space=None):
        if space:
            query = 'cql=(space=%s+and+type=page' % space
        else:
            query = 'cql=(type=page'
        for param in params:
            query += '+and+text~%s' % param
        query += ')'
        return query
