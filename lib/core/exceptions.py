#!/usr/bin/python3


class ConfigParsingError(Exception):
    pass


class InvalidCredentials(Exception):
    pass


class InvalidPlugin(Exception):
    pass


class InvalidResponseFromPlugin(Exception):
    pass


class MissingBotName(Exception):
    pass


class MissingSlackToken(Exception):
    pass
