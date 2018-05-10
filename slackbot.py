#!/usr/bin/python3

from lib.client import SlackBot
from argparse import ArgumentParser
import sys


def run():
    args = parse_args()
    if args.daemon:
        SlackBot()


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
            '-d',
            '--daemon',
            action='store_const',
            const=True,
            dest='daemon',
            help='Run the slackbot daemon. Overrides all other options.'
            )
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    else:
        args = parser.parse_args()
        return args


if __name__ == '__main__':
    run()
