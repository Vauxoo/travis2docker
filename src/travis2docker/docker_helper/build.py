# No plan to use logging here
# pylint: disable=print-used

import glob
import os
import re
import subprocess
import sys


def ssh_keyscan2known_hosts(url, known_hosts_path=None):
    # python3 -c "import build;build.ssh_keyscan2known_hosts('url')"
    if known_hosts_path is None:
        known_hosts_path = os.path.join(os.path.expanduser("~"), ".ssh", "known_hosts")
    cmd = ["ssh-keyscan", url]
    keys_scanned = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip().splitlines()
    with open(known_hosts_path, "r+") as known_hosts_f:
        new_keys_scanned = set(keys_scanned) - set(known_hosts_f.read().splitlines())
        for key_scanned in new_keys_scanned:
            known_hosts_f.write("\n" + key_scanned)


def git_set_remote(path=None):
    # python3 -c "import build;build.git_set_remote('')"
    if path is None:
        path = "/home/odoo/instance"
    git_re = re.compile("([^/|@]+)/([^/]+)/([^/.]+(.git)?)")
    path = os.path.join(path, "*", "**", ".git")
    hosts_scanned = set()
    for git_dir in glob.glob(path, recursive=True):
        git_cmd = ["git", "--work-tree=%s" % os.path.dirname(git_dir), "--git-dir=%s" % git_dir]
        cmd = git_cmd + ["remote", "get-url", "--push", "origin"]
        remote = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip().splitlines()[0]
        git_re_match = git_re.search(remote)

        cmd = git_cmd + ["config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"]
        subprocess.call(cmd)

        if not git_re_match:
            print("Remote not matched %s" % remote)
            continue

        git_re_groups = git_re_match.groups()
        host = git_re_groups[0]

        cmd = git_cmd + ["rev-parse", "--is-shallow-repository"]
        is_shallow = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip().splitlines()[0]
        if is_shallow == 'true':
            if host not in hosts_scanned:
                ssh_keyscan2known_hosts(host)
                hosts_scanned.add(host)
            cmd = git_cmd + ["fetch", "--unshallow"]
            print(' '.join(cmd))
            subprocess.call(cmd)

        ssh_url_dev = "git@%s:%s-dev/%s" % (host, git_re_groups[1], git_re_groups[2])
        cmd = git_cmd + ["remote", "add", "dev", ssh_url_dev]
        print(' '.join(cmd))
        subprocess.call(cmd)

        ssh_url_stb = "git@%s:%s/%s" % (host, git_re_groups[1], git_re_groups[2])
        cmd = git_cmd + ["remote", "set-url", "origin", ssh_url_stb]
        print(' '.join(cmd))
        subprocess.call(cmd)
