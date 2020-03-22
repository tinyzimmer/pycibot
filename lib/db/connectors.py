import os
import json
import gzip
import threading


from ..config import SlackBotConfig as config
from ..logging import SlackBotLogger as logger


basedir = dir_path = os.path.dirname(os.path.realpath(__file__))


class DatabaseConnector(object):

    def __init__(self, **kwargs):
        self.setUp()

    def _get_value(self, subject, key):
        logger.debug(f"Retrieving value '{key}' for '{subject}'")
        return self.get_value(subject, key)

    def _store_value(self, subject, key, value):
        logger.debug(f"Storing value '{key}' for '{subject}'")
        return self.store_value(subject, key, value)


class InMemoryDatabase(DatabaseConnector):

    def setUp(self):
        self.config = config.get("memory")
        self.lock = threading.Lock()
        if self.config:
            if self.config.get("persistence") is True:
                self.persistence_enabled = True
                if self.config.get("db_path"):
                    self.db_path = self.config["db_path"]
                else:
                    self.db_path = os.path.join(basedir, "db.gz")
        self._load_db()

    def _load_db(self):
        self.db = {}
        if self.persistence_enabled:
            if os.path.exists(self.db_path):
                with gzip.open(self.db_path, "rb") as f:
                    self.db = json.loads(f.read().decode())

    def get_value(self, subject, key):
        if self.db.get(subject):
            return self.db[subject].get(key)
        return None

    def store_value(self, subject, key, value):
        with self.lock:
            if not self.db.get(subject):
                self.db[subject] = {}
            self.db[subject][key] = value
            if self.persistence_enabled:
                with gzip.open(self.db_path, "wb") as f:
                    f.write(json.dumps(self.db).encode())
