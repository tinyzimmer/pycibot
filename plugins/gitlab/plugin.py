#!/usr/bin/python3

import gitlab
from lib.builtins import BasePlugin
from plugins.gitlab.database import GitlabDatabase
from threading import Thread
from time import sleep


class InvalidGitlabCredentials(Exception):
    pass


class SlackBotPlugin(BasePlugin):
    hooks = [
                'watch-repo',
                'list-repos',
                'reject-merge',
                'accept-merge',
                'request-merge',
                'delete-branch',
                'schedule-merge'
                ]
    help_pages = [
                {'watch-repo': 'watch-repo <repo> - \
Watches repo for merge requests'},
                {'list-repos': 'list-repos - Lists watched repositories'},
                {'reject-merge': 'reject-merge <mergeid> - \
Reject a merge request'},
                {'accept-merge': 'accept-merge <mergeid> - \
Accept a merge request'},
                {'request-merge': 'request-merge <repo> <src> <dest> - \
Create a merge request'},
                {'delete-branch': 'delete-branch <repo> <branch> - \
Delete a branch'},
                {'schedule-merge': '\
schedule-merge <repo> <src> <dest> <day> <time>'}
                ]

    def __init__(self, threads=True, **kwargs):
        super().__init__(**kwargs)
        self.gitlab_url = self.client.config['gitlab_url']
        self.gitlab_conn = gitlab.Gitlab(
                self.gitlab_url,
                self.client.config['gitlab_token']
                )
        try:
            self.gitlab_conn.auth()
        except:
            raise InvalidGitlabCredentials
        self.session = GitlabDatabase(self.client.dbsession)
        self.default_channel = self.client.config['gitlab_active_channel']
        if threads:
            self.__start_threads()
        self.inprogress_merges = []

    def __start_threads(self):
        Thread(target=self._check_watched_projects).start()
        Thread(target=self._check_scheduled_merges).start()

    def _check_scheduled_merges(self):
        while self.client.running:
            merges = self.session.get_upcoming_merges()
            if len(merges) > 0:
                for merge in merges:
                    msgs = [
                        "<!here> Merge scheduled of %s to %s on %s at %s" % (
                            merge.src,
                            merge.dest,
                            merge.repo,
                            merge.time.strftime("%H:%M PST")
                            ),
                        "I will need three approvals in the channel before then \
for the merge to go through",
                        "To approve this merge say @%s approve %s:%s" % (
                                self.client.name, merge.repo, merge.id
                            )
                        ]
                    for msg in msgs:
                        self.client.send_channel_message(
                            self.default_channel,
                            msg
                        )
                        sleep(1)
            sleep(10)

    def _check_watched_projects(self):
        while self.client.running:
            projects = self.session.get_all_watched_projects()
            for project in projects:
                merge_requests = self._get_merge_requests(project.path)
                if merge_requests:
                    for mr in merge_requests:
                        check = "%s:%s" % (project.path, mr.iid)
                        if not self.session.merge_announced(check) \
                                and mr.state == 'opened':
                            diffs = self._get_merge_request_diffs(mr)
                            title = "Merge Request for %s" % (
                                project.path
                                )
                            content = '\n\n'.join(diffs)
                            self.client.send_channel_message(
                                    self.default_channel,
                                    "<!here> New Merge Request ID: %s" % check
                                    )
                            self.client.send_channel_file(
                                        self.default_channel,
                                        title,
                                        'diff',
                                        content
                                        )
                            self.session.register_announced_merge(check)
            sleep(10)

    def _get_merge_request_diffs(self, mr):
        returned_diffs = []
        diffs = mr.diffs.list()
        for diff in diffs:
            ddiff = mr.diffs.get(diff.id)
            for item in ddiff.diffs:
                returned_diffs.append(item['diff'])
        return returned_diffs

    def _get_merge_requests(self, path):
        project = self._get_project(path)
        if project:
            mrs = project.mergerequests.list()
            if len(mrs) > 0:
                return mrs
            else:
                return None

    def _get_project(self, project):
        index = 1
        while True:
            items = self.gitlab_conn.projects.list(
                page=index, per_page=10
                )
            if len(items) > 0:
                for item in items:
                    if item.path_with_namespace.lower() == project:
                        return item
                index += 1
            else:
                return None

    def _get_branch(self, project, branch):
        try:
            branch = project.branches.get(branch)
            return branch
        except gitlab.exceptions.GitlabGetError:
            return None

    def _create_branch(self, project, branch, ref):
        project = self._get_project(project)
        if project:
            if self._get_branch(project, ref):
                branch = project.branches.create(
                        {
                            'branch_name': branch,
                            'ref': ref
                        }
                    )
                if branch:
                    return branch
        return None

    def schedule_merge(self, repo, src_branch, dest_branch, day, time):
        project = self._get_project(repo)
        if not project:
            return "Could not find %s in Gitlab" % repo
        if not self._get_branch(project, src_branch):
            return "Could not a branch named %s in %s" % (src_branch, repo)
        if not self._get_branch(project, dest_branch):
            return "Could not a branch named %s in %s" % (dest_branch, repo)
        san_time = time.replace(':', '')
        self.session.add_scheduled_merge(
                repo,
                src_branch,
                dest_branch,
                day,
                san_time
                )
        msg_one = "%s will be merged into %s every %s at %s" % (
                    src_branch,
                    dest_branch,
                    day,
                    time
                )
        msg_two = "I will ask for approvals 2 hours before the merge"
        return [msg_one, msg_two]

    def reject_merge_request(self, project, iid):
        mrs = self._get_merge_requests(project)
        for mr in mrs:
            if int(mr.iid) == int(iid):
                mr.delete()

    def accept_merge_request(self, user, project, iid, tag):
        glproject = self._get_project(project)
        mrs = self._get_merge_requests(project)
        for mr in mrs:
            if int(mr.iid) == int(iid):
                target_branch = mr.target_branch
                mr.merge()
        if tag:
            tag = glproject.tags.create(
                    {'tag_name': tag, 'ref': target_branch}
                )
            tag.set_release_description('%s release - Accepted By: %s' % (
                    tag,
                    user['real_name']
                )
            )

    def received_watch(self, channel, user, words):
        try:
            repo = words[1]
        except IndexError:
            return self.client.get_help_page('watch-repo')
        self.client.send_channel_message(
                channel,
                "One second while I look that up for you"
                )
        if self._get_project(repo):
            success, data = self.session.add_watched_project(
                    words[1],
                    user['email']
                    )
            if success:
                return "Okay. I am now watching %s" % repo
            else:
                if data == 'error':
                    return "An error occurred in the database"
                else:
                    messages = [
                            "I am already watching %s." % repo,
                            "It looks like it was requested by %s." % data
                            ]
                    return messages

        else:
            return "Sorry, I can't find a project by the name %s" % \
                    repo

    def received_list_projects(self):
        projects = self.session.get_all_watched_projects()
        messages = []
        if len(projects) > 0:
            messages.append("I am watching the following projects:")
            response = '```%s```' % '\n'.join(
                    [' - %s' % x.path for x in projects]
                )
            messages.append(response)
            return messages
        else:
            return "I am not watching any projects currently"

    def received_reject(self, words):
        try:
            merge_id = words[1]
        except IndexError:
            return self.client.get_help_page('reject-merge')
        project = merge_id.split(':')[0]
        iid = merge_id.split(':')[1]
        self.reject_merge_request(project, iid)
        self.session.remove_announced_merge(merge_id)
        return "Merge Request %s has been rejected" % merge_id

    def received_accept(self, user, words):
        try:
            merge_id = words[1]
        except IndexError:
            return self.client.get_help_page('accept-merge')
        try:
            tag = words[2]
        except IndexError:
            tag = None
        project = merge_id.split(':')[0]
        iid = merge_id.split(':')[1]
        self.accept_merge_request(user, project, iid, tag)
        self._remove_announced_merge(merge_id)
        return "Merge request for %s has been accepted by %s" % (
                    project,
                    user['real_name']
                )

    def received_request(self, user, words):
        try:
            project = self._get_project(words[1])
            if not project:
                return "Could not find a repo named %s" % words[1]
            if project:
                src = words[2]
                dest = words[3]
                if not self._get_branch(project, src):
                    return "Could not find source branch %s on %s" % (
                            src,
                            words[1]
                            )
                elif not self._get_branch(project, dest):
                    return "Could not find destination branch %s on %s" % (
                            dest,
                            words[1]
                            )
                else:
                    mr_title = "%s -> %s Requestor: %s" % (
                            src,
                            dest,
                            user['email']
                            )
                    project.mergerequests.create(
                        {'source_branch': src,
                         'target_branch': dest,
                         'title': mr_title}
                        )
                    return "Merge Request submitted on %s for %s -> %s" % (
                                words[1],
                                src,
                                dest
                            )
        except IndexError:
            return self.client.get_help_page('request-merge')

    def received_delete(self, words):
        try:
            proj_name = words[1]
            branch_name = words[2]
        except IndexError:
            return self.client.get_help_page('delete-branch')
        project = self._get_project(proj_name)
        if not project:
            return "Could not find project %s" % proj_name
        else:
            branch = self._get_branch(project, branch_name)
            if not branch:
                return "Could not find branch %s on %s" % (words[2], words[1])
            else:
                branch.delete()
                return "Removed branch %s from %s" % (words[2], words[1])

    def received_schedule_merge(self, channel, user, words):
        try:
            repo = words[1]
            src_branch = words[2]
            dest_branch = words[3]
            day = words[4]
            time = words[5]
        except IndexError:
            return self.client.get_help_page('schedule-merge')
        return self.schedule_merge(repo, src_branch, dest_branch, day, time)

    def on_recv(self, channel, user, words):
        if user['display_name'] in self.client.admins:
            if words[0] == 'watch-repo':
                return self.received_watch(channel, user, words)
            if words[0] == 'list-repos':
                return self.received_list_projects()
            if words[0] == 'reject-merge':
                return self.received_reject(words)
            if words[0] == 'accept-merge':
                return self.received_accept(user, words)
            if words[0] == 'request-merge':
                return self.received_request(user, words)
            if words[0] == 'delete-branch':
                return self.received_delete(words)
            if words[0] == 'schedule-merge':
                return self.received_schedule_merge(channel, user, words)
        elif words[0] in self.hooks:
            return "Access Denied"
