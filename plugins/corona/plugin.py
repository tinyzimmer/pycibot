#!/usr/bin/python3

from lib.builtins import BasePlugin
from datetime import datetime
import requests
import json

from prettytable import PrettyTable


BASE_URL = "https://corona.lmao.ninja"
KEYS = ['cases', 'todayCases', 'deaths', 'todayDeaths', 'recovered', 'active', 'critical', 'casesPerOneMillion']
COLUMNS = ['Country', 'Cases', 'Cases (today)', 'Deaths', 'Deaths (today)', 'Recovered', 'Active', 'Critical', 'Per Million']

def format_num(number):
    return f'{int(number):,}'


class SlackBotPlugin(BasePlugin):

    hooks = ['corona']
    help_pages = [{'corona': 'corona <country> [state] - get the latest corona statistics'}]

    def setUp(self):
        pass

    def do(self, url):
        return requests.get(url).json()

    def get_worldwide(self):
        return self.do(f"{BASE_URL}/all")

    def get_country(self, country):
        return self.do(f"{BASE_URL}/countries/{country.lower()}")

    def get_state_data(self, state):
        res = self.do(f"{BASE_URL}/states")
        out = [x for x in res if x['state'] == state.title()]
        if len(out) == 1:
            return out[0]
        return None

    def to_row(self, data):
        out = []
        for key in KEYS:
            if data.get(key):
                out.append(format_num(data[key]))
            else:
                out.append("---")
        return out

    def on_recv(self, channel, user, cmd, words):
        if len(words) == 0:
            return self.client.get_help_page("corona")
        worldwide_data = self.get_worldwide()
        country_data = self.get_country(words[0])
        state_data = None
        if len(words) > 1:
            state_data = self.get_state_data(' '.join(words[1:]))
        last_updated = datetime.fromtimestamp(
            int(worldwide_data.get('updated')) / 1000
        ).strftime("%a, %d %b %Y %H:%M:%S UTC")
        t = PrettyTable(COLUMNS)
        t.add_row(['Worldwide', *self.to_row(worldwide_data)])
        t.add_row(['---'] * 9)
        t.add_row([country_data.get('country'), *self.to_row(country_data)])
        if state_data:
            t.add_row([f'State: {state_data.get("state")}', *self.to_row(state_data)])
        return f"*Last Updated:* _{last_updated}_\n```\n{t}\n```"
