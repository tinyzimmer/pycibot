#!/usr/bin/python3

import jenkins
from xml.etree import ElementTree as et
from sqlalchemy import Column, Integer, String
from threading import Thread
from lib.colors import colors
from time import sleep
from datetime import datetime
from lib.builtins import BasePlugin
from six.moves.urllib.request import Request
import sys
import re


class SlackBotPlugin(BasePlugin):

    def __init__(self, threads=True, **kwargs):
        self.hooks = [
                'build',
                'get-config',
                'copy-job',
                'get-latest-build',
                'watch-job',
                'list-jobs',
                'get-job-options',
                'get-submods'
                ]
        self.help_pages = [
                {'build': 'build <job> [param=value]'},
                {'get-config': 'get-config <job>'},
                {'copy-job': 'copy-job <source> <destination> - \
Clones a Jenkins Job'},
                {'get-latest-build': 'get-latest-build <job>'},
                {'watch-job': 'watch-job <job>'},
                {'list-jobs': 'list-jobs - Lists watched Jenkins jobs'},
                {'get-job-options': 'get-job-options <job> - \
Get options for job'},
                {'get-submods': 'get-submods <job>'}
                ]
        super().__init__(**kwargs)
        self.username = self.client.config['jenkins_username']
        self.token = self.client.config['jenkins_token']
        self.hostname = self.client.config['jenkins_hostname']
        self.default_channel = self.client.config['jenkins_active_channel']
        self.server = jenkins.Jenkins(
                self.hostname,
                username=self.username,
                password=self.token
            )
        self.db = self.client.dbsession
        self.session = self.db.session
        self.__create_tables()
        if threads:
            self.__start_threads()

    def __create_tables(self):

        class WatchedBuilds(self.db.base):
            __tablename__ = 'watched_builds'
            id = Column(Integer, primary_key=True)
            name = Column(String(64), unique=True)
            last_announce = Column(Integer)

        self.WatchedBuilds = WatchedBuilds
        try:
            self.WatchedBuilds.__table__.create(self.session.bind)
        except Exception as e:
            if 'already exists' in str(e):
                sys.stdout.write(
                    "%sWatchedBuilds already exists in local db\n" % (
                        colors.WARNING
                    )
                )
            else:
                sys.stdout.write("%s%s\n" % (colors.FAIL, e))
        self.db.ensure_table_defs()

    def __start_threads(self):
        Thread(target=self._check_watched_jobs).start()

    def _build_job_attachment(self, job, info):
        if info['result'] == "SUCCESS":
            color = "#36a64f"
        else:
            color = "#ff0000"
        url = info['url'].replace(
                'http://localhost:8080',
                self.hostname
            )
        attachment = {
            "fallback": "%s Summary" % info['fullDisplayName'],
            "color": color,
            "pretext": "Latest build for %s" % job,
            "title": info['fullDisplayName'],
            "title_link": url,
            "text": "Build Result: %s" % info['result']
        }
        return attachment

    def _check_watched_jobs(self):
        while self.client.running:
            jobs = self._get_watched_jobs()
            for job in jobs:
                last_build = self._get_last_build_number(job.name)
                if job.last_announce:
                    if int(last_build) == int(job.last_announce):
                        continue
                if not job.last_announce or job.last_announce != last_build:
                    info = self.server.get_build_info(job.name, last_build)
                    attachment = self._build_job_attachment(job.name, info)
                    self.client.send_channel_message(
                            self.default_channel,
                            '',
                            [attachment]
                        )
                    job.last_announce = last_build
                    self.session.add(job)
                    self.session.commit()
            sleep(10)

    def _trim_console(self, output):
        lines = output.splitlines()
        while len(lines) > 0:
            line = lines.pop(0)
            if "EXECUTE USER SCRIPT" not in line:
                continue
            else:
                break
        return '\n'.join(lines)

    def _get_job(self, job):
        try:
            config = self.server.get_job_config(job)
            return config
        except jenkins.NotFoundException:
            return None

    def _get_watched_jobs(self):
        jobs = self.session.query(self.WatchedBuilds).all()
        if jobs:
            return jobs
        else:
            return []

    def _get_last_build_number(self, job):
        number = self.server.get_job_info(
                job
                )['lastCompletedBuild']['number']
        return number

    def _parse_choice_parameter(self, element):
        chelement = [x for x in element.getchildren() if x.tag == 'choices'][0]
        choices = [x.text for x in chelement.getchildren()[0].getchildren()]
        return choices

    def _get_parameter_default(self, element):
        default = [
            x.text for x in element.getchildren()
            if x.tag == 'defaultValue'
        ][0]
        return default or 'None'

    def _format_opts_to_msg(self, job, opts):
        msg = '> *Options for %s*\n>>>' % job
        for item in opts:
            for key, value in item.items():
                first = True
                if isinstance(value, list):
                    sanitized_list = []
                    for item in value:
                        if item and first:
                            sanitized_list.append("*`%s`*" % item)
                            first = False
                        elif not item and first:
                            sanitized_list.append("*`None`*")
                            first = False
                        elif item:
                            sanitized_list.append("`%s`" % item)
                        else:
                            sanitized_list.append("`None`")
                    text = "*%s:*\n>%s\n" % (
                            key,
                            " ".join(sanitized_list)
                        )
                elif isinstance(value, str) \
                        and value == 'true' or value == 'false':
                    if value == 'true':
                        text = '*%s:*\n>*`True`* `False`\n' % key
                    elif value == 'false':
                        text = '*%s:*\n>`True` *`False`*\n' % key
                elif isinstance(value, str):
                    text = '*%s:*\n>_Default:_ `%s`\n' % (key, value)
                else:
                    text = '*%s:*\n>_Unparsed option_\n' % key
            msg = "%s%s" % (msg, text)
        return msg

    def parse_job_options(self, job, to_msg=True):
        config = self._get_job(job)
        if not config:
            return "Sorry, I could not find that job."
        tree = et.fromstring(config)
        parent = tree.find(
                './/parameterDefinitions'
                )
        opts = []
        for item in parent.getchildren():
            name = [x.text for x in item.getchildren() if x.tag == 'name'][0]
            if item.tag == 'hudson.model.ChoiceParameterDefinition':
                choices = self._parse_choice_parameter(item)
                opt = {name: choices}
            elif item.tag == 'hudson.model.StringParameterDefinition':
                default = self._get_parameter_default(item)
                opt = {name: default}
            elif item.tag == 'hudson.model.BooleanParameterDefinition':
                default = self._get_parameter_default(item)
                opt = {name: default}
            else:
                opt = {name: None}
            opts.append(opt)
        if to_msg is True:
            return self._format_opts_to_msg(job, opts)
        elif to_msg is False:
            return opts

    def manage_build_job(self, channel, words, opts):
        job = words[1]
        params = {}
        for arg in words[2:]:
            key, value = self.validate_build_arg(opts, arg)
            if key and value:
                params[key] = value
            else:
                return "Invalid argument for %s - %s" % (job, arg)
        build_params = self.populate_build_args(opts, params)
        bn = self.server.get_job_info(job)['nextBuildNumber']
        msg = "> *Building %s #%s with the following parameters:*\n>>>" % (
                job,
                str(bn)
            )
        for key, value in build_params.items():
            if value == '':
                value = None
            text = "%s: `%s`\n" % (key, value)
            msg = "%s%s" % (msg, text)
        self.server.build_job(job, build_params)
        Thread(target=self.monitor_build, args=[channel, job, bn]).start()
        return [msg, "I'll let you know here when it's finished"]

    def monitor_build(self, channel, job, bn):
        st_time = datetime.now()
        while True:
            try:
                info = self.server.get_build_info(job, bn)
                if info['result'] == "SUCCESS" or info['result'] == "FAILURE":
                    attachment = self._build_job_attachment(job, info)
                    self.client.send_channel_message(
                            channel,
                            '',
                            [attachment]
                        )
                    break
            except jenkins.NotFoundException:
                now = datetime.now()
                elapsed = now - st_time
                if elapsed.seconds > 3600:
                    msg = "Timed out waiting for %s %s" % (job, bn)
                    self.client.send_channel_message(channel, msg)
                    break
                else:
                    pass
            sleep(3)

    def populate_build_args(self, opts, params):
        build_params = {}
        for opt in opts:
            for key, value in opt.items():
                try:
                    build_params[key] = params[key]
                except KeyError:
                    if isinstance(value, str):
                        build_params[key] = value or ''
                    elif isinstance(value, list):
                        build_params[key] = value[0] or ''
        return build_params

    def validate_build_arg(self, opts, arg):
        try:
            param, val = arg.split('=')
        except:
            return None, None
        for opt in opts:
            for key, value in opt.items():
                if isinstance(value, str):
                    if key.upper() == param.upper():
                        return key, val
                elif isinstance(value, list):
                    for item in value:
                        if not item:
                            pass
                        elif val.upper() == item.upper():
                            return key, item
        return None, None

    def branch_job(self, job, branch):
        config = self._get_job(job)
        if config:
            tree = et.fromstring(config)
            tree.find(
                    './/hudson.plugins.git.BranchSpec/name'
                    ).text = '*/%s' % branch
            new_name = "%s-%s" % (branch, job)
            new_config = et.tostring(tree).decode('utf-8')
            self.server.create_job(new_name, new_config)
            return new_name

    def add_watched_job(self, job):
        watched_job = self.WatchedBuilds(
                name=job
                )
        try:
            self.session.add(watched_job)
            self.session.commit()
            return True
        except Exception as e:
            return e

    def received_copy(self, words):
        try:
            src = words[1]
            dest = words[2]
        except IndexError:
            return self.client.get_help_page('copy-job')
        try:
            self.server.copy_job(src, dest)
            return "Successfully created %s from %s" % (dest, src)
        except:
            return "Failed to copy %s" % src

    def received_get_latest_build(self, channel, words):
        try:
            job = words[1]
        except IndexError:
            return self.client.get_help_page('get-latest-build')
        if not self._get_job(job):
            return "Could not find job named %s" % job
        number = self._get_last_build_number(job)
        console_output = self.server.get_build_console_output(job, number)
        trimmed_output = self._trim_console(console_output)
        if (len(trimmed_output.strip())) == 0:
            trimmed_output = console_output
        if len(trimmed_output.splitlines()) >= 250:
            build_info = self.server.get_build_info(job, number)
            fixed_url = build_info['url'].replace(
                    'http://localhost:8080',
                    self.hostname
                    )
            console_url = "%sconsole" % fixed_url
            message = "Too long to upload. Link to output - %s" % console_url
            return message
        else:
            self.client.send_channel_file(
                    channel,
                    "Latest build for %s" % job,
                    'shell',
                    str(trimmed_output)
                    )
            return None

    def received_watch_job(self, channel, words):
        try:
            job = words[1]
        except IndexError:
            return self.client.get_help_page('watch-job')
        self.client.send_channel_message(
                channel,
                "One second while I look that up..."
                )
        if self._get_job(words[1]):
            response = self.add_watched_job(job)
            if response is True:
                return "Watching builds for %s" % job
            else:
                return response
        else:
            return "I could not find a job by the name of %s" % job

    def received_list_jobs(self):
        jobs = self._get_watched_jobs()
        messages = []
        if len(jobs) > 0:
            messages.append("I am watching the following Jenkins jobs:")
            response = '```%s```' % '\n'.join([x.name for x in jobs])
            messages.append(response)
            return messages
        else:
            return "I am not watching any Jenkins jobs currently."

    def received_get_job_opts(self, words):
        try:
            job = words[1]
        except IndexError:
            return self.client.get_help_page('get-job-options')
        return self.parse_job_options(job)

    def received_build_job(self, channel, words):
        try:
            job = words[1]
        except IndexError:
            return self.client.get_help_page('build')
        opts = self.parse_job_options(job, to_msg=False)
        if isinstance(opts, str):
            return opts
        else:
            return self.manage_build_job(channel, words, opts)

    def received_get_job_config(self, channel, words):
        try:
            job = words[1]
        except IndexError:
            return self.client.get_help_page('get-config')
        config = self._get_job(job)
        if not config:
            return "Could not find a job named %s" % job
        else:
            self.client.send_channel_file(
                    channel,
                    job,
                    'xml',
                    config
                    )

    def received_get_submodule_stats(self, channel, words):
        try:
            job = words[1]
        except IndexError:
            return self.client.get_help_page('get-submods')
        exists = self._get_job(job)
        if not exists:
            return "Could not find job named %s" % job
        req = Request("%s/job/%s/ws/.gitmodules" % (self.hostname, job))
        response = self.server.jenkins_open(req)
        if response:
            submodules = re.findall("\[submodule.*/(.*)\"\]", response)
            paths = re.findall("path\s*=\s*(.*)", response)
            urls = re.findall("url\s*=\s*(.*)", response)
            group = zip(submodules, zip(paths, urls))
            submodule_dict = dict(
                    [(z[0], {'path': z[1][0], 'url':z[1][1]}) for z in group]
                )
        return str(submodule_dict)

    def on_recv(self, channel, user, words):
        if user['display_name'] in self.client.admins:
            if words[0] == 'copy-job':
                return self.received_copy(words)
            if words[0] == 'get-latest-build':
                return self.received_get_latest_build(channel, words)
            if words[0] == 'watch-job':
                return self.received_watch_job(channel, words)
            if words[0] == 'list-jobs':
                return self.received_list_jobs()
            if words[0] == 'get-job-options':
                return self.received_get_job_opts(words)
            if words[0] == 'build':
                return self.received_build_job(channel, words)
            if words[0] == 'get-config':
                return self.received_get_job_config(channel, words)
            if words[0] == 'get-submods':
                return self.received_get_submodule_stats(channel, words)
        elif words[0] in self.hooks:
            return "Access Denied"
