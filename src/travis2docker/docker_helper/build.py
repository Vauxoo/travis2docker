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

    # Clear current known hosts
    cmd = ["ssh-keygen", "-R", url]
    print(' '.join(cmd))
    subprocess.call(cmd)

    # Scan new key of host and store
    cmd = ["ssh-keyscan", "-p", "22", url]
    print(' '.join(cmd))
    keys_scanned = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip()
    with open(known_hosts_path, "r+") as known_hosts_f:
        known_hosts_f.write("\n" + keys_scanned)


def git_set_remote(path=None):
    # python3 -c "import build;build.git_set_remote('')"
    if path is None:
        # /home/odoo/instance/odoo spends a lot of time
        path = "/home/odoo/instance/extra_addons"
    git_re = re.compile("([^/|@]+)/([^/]+)/([^/.]+(.git)?)")
    # TODO: Support ssh url
    path = os.path.join(path, "*", "**", ".git")
    hosts_scanned = set()
    for git_dir in glob.glob(path, recursive=True):
        git_cmd = ["git", "--work-tree=%s" % os.path.dirname(git_dir), "--git-dir=%s" % git_dir]
        cmd = git_cmd + ["remote", "get-url", "--push", "origin"]
        remote = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip().splitlines()[0]
        git_re_match = git_re.search(remote)

        # Configure to fetch all branches (not only the single-branch)
        cmd = git_cmd + ["config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"]
        subprocess.call(cmd)

        if not git_re_match:
            print("Remote not matched %s" % remote)
            continue

        git_re_groups = git_re_match.groups()
        host = git_re_groups[0]
        org = git_re_groups[1]
        repo = git_re_groups[2]

        # Transform https url to ssh format
        ssh_url_stb = "git@%s:%s/%s" % (host, org, repo)
        cmd = git_cmd + ["remote", "set-url", "origin", ssh_url_stb]
        print(' '.join(cmd))
        subprocess.call(cmd)

        # Unshallow repository
        cmd = git_cmd + ["rev-parse", "--is-shallow-repository"]
        is_shallow = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip().splitlines()[0]
        if is_shallow == 'true':
            if host not in hosts_scanned:
                ssh_keyscan2known_hosts(host)
                hosts_scanned.add(host)
            cmd = git_cmd + ["fetch", "--unshallow"]
            print(' '.join(cmd))
            subprocess.call(cmd)

        # Add extra remote if "stb" so add "dev" if "dev" so add "stb"
        new_org = org.replace("-dev", "") if "-dev" in org else "%s-dev" % org
        new_remote = "dev" if "dev" in new_org else "stb"
        ssh_url_dev = "git@%s:%s/%s" % (host, new_org, repo)
        cmd = git_cmd + ["remote", "add", new_remote, ssh_url_dev]
        print(' '.join(cmd))
        subprocess.call(cmd)
