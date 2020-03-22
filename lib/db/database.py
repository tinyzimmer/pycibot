import inspect

from .connectors import InMemoryDatabase
from ..config import SlackBotConfig as config
from ..logging import SlackBotLogger as logger


def get_caller():
    caller = inspect.stack()[2][1]
    return caller.split("/")[-2]


class DatabaseSession(object):

    def __init__(self):
        if not config.get_all():
            logger.debug("No db configuration provided, using default in-memory without persistence")
            engine = InMemoryDatabase
        else:
            engine_name = list(config.get_all().keys())[0]
            if engine_name == 'memory':
                logger.debug(f"Configuring in-memory db engine with opts: {config.get('memory')}")
                engine = InMemoryDatabase
        self.engine = engine()

    def get_value(self, key):
        return self.engine._get_value(get_caller(), key)

    def store_value(self, key, value):
        return self.engine._store_value(get_caller(), key, value)
