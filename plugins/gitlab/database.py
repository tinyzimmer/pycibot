#!/usr/bin/python3

from sqlalchemy import Column, Integer, String, Time, Boolean
from datetime import datetime, date
from lib.colors import colors
import pytz
import sys


class GitlabDatabase(object):

    def __init__(self, db):
        self.db = db
        self.session = db.session
        self.scheduled_merges = {}
        self.weekdays = {
                '0': 'sunday',
                '1': 'monday',
                '2': 'tuesday',
                '3': 'wednesday',
                '4': 'thursday',
                '5': 'friday',
                '6': 'saturday',
            }
        self.__create_tables()

    def __create_tables(self):

        class WatchedProjects(self.db.base):
            __tablename__ = 'watched_projects'
            id = Column(Integer, primary_key=True)
            path = Column(String(32), unique=True)
            requestor = Column(String(32))

        class AnnouncedMergeRequests(self.db.base):
            __tablename__ = "announced_merges"
            id = Column(Integer, primary_key=True)
            merge_id = Column(String(32), unique=True)

        class ScheduledMerges(self.db.base):
            __tablename__ = "scheduled_merges"
            id = Column(Integer, primary_key=True)
            repo = Column(String(32))
            src = Column(String(32))
            dest = Column(String(32))
            dow = Column(Integer)
            time = Column(Time)
            announced = Column(Boolean)

        self.WatchedProjects = WatchedProjects
        self.AnnouncedMergeRequests = AnnouncedMergeRequests
        self.ScheduledMerges = ScheduledMerges
        try:
            self.WatchedProjects.__table__.create(self.session.bind)
        except Exception as e:
            if 'already exists' in str(e):
                sys.stdout.write(
                    "%sWatchedProjects already exists in local db\n" % (
                        colors.WARNING
                    )
                )
            else:
                sys.stdout.write("%s%s\n" % (colors.FAIL, e))
        try:
            self.AnnouncedMergeRequests.__table__.create(self.session.bind)
        except Exception as e:
            if 'already exists' in str(e):
                sys.stdout.write(
                    "%sAnnouncedMergeRequests already exists in local db\n" % (
                        colors.WARNING
                    )
                )
            else:
                sys.stdout.write("%s%s\n" % (colors.FAIL, e))
        try:
            self.ScheduledMerges.__table__.create(self.session.bind)
        except Exception as e:
            if 'already exists' in str(e):
                sys.stdout.write(
                    "%sScheduledMerges already exists in local db\n" % (
                        colors.WARNING
                    )
                )
            else:
                sys.stdout.write("%s%s\n" % (colors.FAIL, e))
        self.db.ensure_table_defs()

    def _day_to_int(self, day_str):
        for integer, string in self.weekdays.items():
            if str(day_str).lower() == str(string).lower():
                return integer
        return None

    def _int_to_day(self, day_int):
        for integer, string in self.weekdays.items():
            if int(integer) == int(day_int):
                return string
        return None

    def _get_time_pst(self):
        now = pytz.utc.localize(
                datetime.utcnow()
            ).astimezone(pytz.timezone('US/Pacific'))
        return now

    def register_announced_merge(self, check_id):
        announced = self.AnnouncedMergeRequests(merge_id=check_id)
        self.session.add(announced)
        self.session.commit()

    def remove_announced_merge(self, check_id):
        announced = self.session.query(
                self.AnnouncedMergeRequests
                ).filter_by(merge_id=check_id).first()
        self.session.delete(announced)
        self.session.commit()

    def merge_announced(self, check_id):
        announced = self.session.query(
                self.AnnouncedMergeRequests
                ).all()
        for item in announced:
            if item.merge_id == check_id:
                return True
        return False

    def get_upcoming_merges(self):
        merges = []
        now = self._get_time_pst()
        scheduled_merges = self.session.query(
                self.ScheduledMerges
                ).all()
        for merge in scheduled_merges:
            day_str = self._int_to_day(merge.dow)
            if now.strftime('%A').lower() == day_str.lower() \
                    and not merge.announced:
                delta = datetime.combine(date.today(), merge.time) \
                    - datetime.combine(date.today(), now.time())
                if 7200 > delta.seconds > 0 or 0 > delta.seconds > -7200:
                    merges.append(merge)
                    merge.announced = True
                    self.session.add(merge)
                    self.session.commit()
        return merges

    def get_watched_project(self, project):
        lookup = self.session.query(
                self.WatchedProjects
                ).filter_by(path=project).first()
        if lookup:
            return lookup
        else:
            return False

    def get_all_watched_projects(self):
        projects = self.session.query(
                self.WatchedProjects
                ).all()
        if projects:
            return projects
        else:
            return []

    def add_watched_project(self, project, user):
        lookup = self.get_watched_project(project)
        if not lookup:
            new_project = self.WatchedProjects(
                    path=project,
                    requestor=user
                    )
            try:
                self.session.add(new_project)
                self.session.commit()
                return True, None
            except:
                self.session.rollback()
                return False, 'error'
        elif lookup:
            return False, lookup.requestor

    def add_scheduled_merge(self, repo, src, dest, dow, time):
        day_int = self._day_to_int(dow)
        time_obj = datetime.strptime("%s PST" % time, '%H%M %Z')
        scheduled_merge = self.ScheduledMerges(
                repo=repo,
                src=src,
                dest=dest,
                dow=day_int,
                time=time_obj.time()
            )
        self.session.add(scheduled_merge)
        self.session.commit()
