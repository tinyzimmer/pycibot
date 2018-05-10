#!/usr/bin/python3

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta


class DatabaseSession(object):

    class NamingDeclarativeMeta(DeclarativeMeta):
        def __init__(cls, classname, bases, dict_):
            if '__name__' in cls.__dict__:
                cls.__name__ = classname = cls.__dict__['__name__']
            DeclarativeMeta.__init__(cls, classname, bases, dict_)

    def __init__(self):
        self.__setup_scoped_session()
        self.base.metadata.create_all(self.engine)

    def __setup_scoped_session(self):
        basedir = os.path.abspath(os.path.dirname(__file__))
        self.engine = create_engine(
            'sqlite:///%s' % os.path.join(basedir, 'data.sqlite'),
            connect_args={
                'check_same_thread': False
                }
        )
        self.base = declarative_base(metaclass=self.NamingDeclarativeMeta)
        Scoped = scoped_session(
            sessionmaker(
                autoflush=True,
                autocommit=False,
                bind=self.engine
                )
            )
        self.session = Scoped()

    def cycle_database(self):
        self.base.metadata.drop_all(self.engine)
        self.ensure_table_defs()

    def ensure_table_defs(self):
        self.__setup_scoped_session()
        self.base.metadata.create_all(self.engine)
