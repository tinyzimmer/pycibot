#!/usr/bin/python3

from plugins.jenkins.plugin import SlackBotPlugin as JenkinsInterface
from plugins.gitlab.plugin import SlackBotPlugin as GitlabInterface
from lib.builtins import BasePlugin


class SlackBotPlugin(BasePlugin):

    hooks = ['setup-project']
    help_pages = [
                {'setup-project': 'setup-project <project_name> <source_repo:branch> \
<source_build_job>\nBranch defaults to master'}
                ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.jenkins = JenkinsInterface(client=self.client, threads=False)
        self.gitlab = GitlabInterface(client=self.client, threads=False)

    def received_setup_project(self, words):
        try:
            name = words[1]
            repo_props = words[2].split(':')
            build_job = words[3]
        except IndexError:
            return self.client.get_help_page('setup-project')
        if len(repo_props) == 1:
            repo = words[2]
            ref = 'master'
        else:
            repo = repo_props[0]
            ref = repo_props[1]
        job = self.jenkins._get_job(build_job)
        if job:
            new_branch = self.gitlab._create_branch(repo, name, ref)
            if new_branch:
                new_job = self.jenkins.branch_job(build_job, name)
                url = "%s/job/%s" % (self.jenkins.hostname, new_job)
                return "%s branched off %s:%s and configured at %s" % (
                        name,
                        repo,
                        ref,
                        url
                        )
            else:
                return "Could not create new branch from %s" % words[2]
        else:
            return "Could not find Jenkins job %s" % words[3]

    def on_recv(self, channel, user, words):
        if words[0] == 'setup-project':
            return self.received_setup_project(words)
