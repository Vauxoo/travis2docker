# No plan to use logging here
# pylint: disable=print-used

import glob
import os
import re
import subprocess
import sys


def git_set_remote(path=None):
    # python3 -c "import build;build.git_set_remote('')"
    if path is None:
        path = "/home/odoo/instance"
    git_re = re.compile("([^/|@]+)/([^/]+)/([^/.]+(.git)?)")
    path = os.path.join(path, "*", "**", ".git")
    for git_dir in glob.glob(path, recursive=True):
        git_cmd = ["git", "--work-tree=%s" % os.path.dirname(git_dir), "--git-dir=%s" % git_dir]
        cmd = git_cmd + ["remote", "get-url", "--push", "origin"]
        remote = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip().splitlines()[0]
        git_re_match = git_re.search(remote)
        if not git_re_match:
            print("Remote not matched %s" % remote)
            continue

        git_re_groups = git_re_match.groups()
        ssh_url_stb = "git@%s:%s/%s" % (git_re_groups[0], git_re_groups[1], git_re_groups[2])
        cmd = git_cmd + ["remote", "set-url", "origin", ssh_url_stb]
        print(' '.join(cmd))
        subprocess.call(cmd)

        ssh_url_dev = "git@%s:%s-dev/%s" % (git_re_groups[0], git_re_groups[1], git_re_groups[2])
        cmd = git_cmd + ["remote", "add", "dev", ssh_url_dev]
        print(' '.join(cmd))
        subprocess.call(cmd)

        cmd = git_cmd + ["config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"]
        print(' '.join(cmd))
        subprocess.call(cmd)
