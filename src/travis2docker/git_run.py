# pylint: disable=useless-object-inheritance,print-used,except-pass
from __future__ import print_function

import os
import re
import subprocess


def decode_utf(field):
    try:
        return field.decode('utf-8')
    except UnicodeDecodeError:
        return ''


class GitRun(object):
    def __init__(self, repo_git, path, path_prefix_repo=False):
        self.repo_git = repo_git
        if path_prefix_repo:
            path = os.path.join(path, self.url2dirname(repo_git))
        self.path = path
        self.host, self.owner, self.repo = self.get_data_url(repo_git)

    @staticmethod
    def get_data_url(repo_git, no_user=True):
        host, owner, repo = False, False, False
        repo_git_sub = repo_git.replace(':', '/')
        if no_user:
            repo_git_sub = re.sub('.+@', '', repo_git_sub)
        repo_git_sub = re.sub('.git$', '', repo_git_sub)
        match_object = re.search(r'(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<repo>[^/]+)', repo_git_sub)
        if match_object:
            host = match_object.group("host")
            owner = match_object.group("owner")
            repo = match_object.group("repo")
        elif os.path.isdir(repo_git):
            host = 'local'
            owner = os.path.basename(repo_git)
            repo = os.path.basename(os.path.dirname(repo_git))
        return host, owner, repo

    @staticmethod
    def url2dirname(url):
        for invalid_char in '@:/#':
            url = url.replace(invalid_char, '_')
        return url

    def checkout_bare(self, branch):
        return self.run(['symbolic-ref', 'HEAD', branch])

    def get_config_data(self, field=None):
        if field is None:
            field = "-l"
        res = self.run(["config", field])
        if res:
            res = res.strip("\n ")
        return res

    def run(self, cmd):
        """Execute git command in bash"""
        cmd = ['git', '--git-dir=%s' % self.path] + cmd
        print("cmd list", cmd)
        print("cmd", ' '.join(cmd))
        res = None
        try:
            res = subprocess.check_output(cmd)
        except BaseException:
            pass
        if res:
            try:
                res = res.decode()
            except UnicodeDecodeError:
                res = res.decode('utf-8')
        return res

    def get_ref_data(self, refs=None, fields=None):
        if refs is None:
            refs = ['refs/heads']
        if fields is None:
            fields = []
        if 'refname' not in fields:
            fields.append('refname')
        # fields = ['refname', 'objectname', 'committerdate:iso8601',
        #           'authorname', 'authoremail','subject','committername',
        #           'committeremail']
        fmt = "%00".join(["%(" + field + ")" for field in fields])
        git_refs = self.run(['for-each-ref', '--format', fmt, '--sort=refname'] + refs)
        git_refs = git_refs.strip()
        refs = [[decode_utf(field) for field in line.split('\x00')] for line in git_refs.split('\n')]
        res = {}
        for data_field in refs:
            subres = dict(zip(fields, data_field))
            res[subres.pop('refname')] = subres
        return res

    def update(self):
        """Get a repository git or update it"""
        if not os.path.isdir(os.path.join(self.path)):
            os.makedirs(self.path)
        if not os.path.isdir(os.path.join(self.path, 'refs')):
            subprocess.check_output(['git', 'clone', '--bare', self.repo_git, self.path])
        self.run(['gc', '--auto', '--prune=all'])
        self.run(['fetch', '-p', 'origin', '+refs/heads/*:refs/heads/*'])
        # github support
        self.run(['fetch', 'origin', '+refs/pull/*/head:refs/pull/*'])
        # gitlab support
        self.run(['fetch', 'origin', '+refs/merge-requests/*/head:refs/pull/*'])

    def show_file(self, git_file, sha):
        result = self.run(["show", "%s:%s" % (sha, git_file)])
        return result

    def get_sha(self, revision):
        result = self.run(["rev-parse", revision])
        return result if isinstance(result, list) else (result or '').strip(' \n')
