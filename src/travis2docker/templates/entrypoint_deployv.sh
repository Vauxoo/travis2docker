#!/usr/bin/env python

from __future__ import print_function

import os
import subprocess
import time
import pwd


def start_psql():
    # Start postgresql service
    if not str2bool(os.environ.get("START_PSQL", True)):
        return
    cmd = "/etc/init.d/postgresql start "
    subprocess.Popen(
        cmd, shell=True, env=os.environ, stdin=None, stdout=None, stderr=None
    )
    print("Waiting to start psql service", end="")
    count = 0
    max_count = 250
    while True:
        print(".", end="")
        psql_subprocess = subprocess.Popen(
            ["psql", "-XtA", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        psql_subprocess.wait()
        psql_out = psql_subprocess.stderr.read()
        if b"rol" in psql_out and b"does not exist" in psql_out:
            psql_error = False
        elif psql_out:
            psql_error = True
        else:
            psql_error = False
        if not psql_error or count > max_count:
            break
        time.sleep(4)
        count += 1
    if not psql_error:
        print("...psql service started.")
    else:
        raise RuntimeError("PSQL %s not started." % os.environ.get("PSQL_VERSION", ""))

    # Fix flaky error when run instance to connect more info:
    # https://www.odoo.com/es_ES/forum/ayuda-1/question/internal-error-index-10107 # noqa
    cmd = [
        "psql",
        os.environ["ODOORC_DB_NAME"],
        "-XtAc",
        "REINDEX INDEX ir_translation_src_hash_idx;",
    ]
    try:
        popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if popen.wait() == 0:
            print("Reindex created: ", cmd)
    except BaseException:
        pass
    return True


def list_modules(modules_path):
    main_repo_path = os.environ["MAIN_REPO_FULL_PATH"]
    list_modules = []
    excluded_modules = set([module.strip() for module in os.environ.get("EXCLUDE", "").split(",") if module.strip()])
    for i in os.listdir(main_repo_path):
        if i in excluded_modules:
            continue
        manifest = os.path.join(main_repo_path, i, "__manifest__.py")
        if os.path.isfile(manifest):
            manifest_data = eval(open(manifest).read())
            if not manifest_data.get("installable", True):
                continue
            list_modules.append(i)
    return list_modules


def is_root():
    return pwd.getpwuid(os.getuid())[0] == "root"


def str2bool(string):
    return str(string or "").lower() in ["1", "true", "yes"]


def start_odoo():
    if not str2bool(os.environ.get("START_ODOO", True)):
        return
    modules = list_modules(os.environ["MAIN_REPO_FULL_PATH"])
    test_enable = str2bool(os.environ.get("TEST_ENABLE", True))
    cmd = ["/home/odoo/instance/odoo/odoo-bin"]
    psql_cmd = [
        "psql",
        os.environ["ODOORC_DB_NAME"],
        "-XtAc",
        "SELECT 1 FROM res_users LIMIT 1;",
    ]
    if is_root():
        cmd = ["sudo", "-u", "odoo"] + cmd
        psql_cmd = ["sudo", "-u", "postgres"] + psql_cmd

    try:
        subprocess.check_output(psql_cmd)
        database_created = True
    except subprocess.CalledProcessError:
        database_created = False

    if not database_created:
        cmd.extend(["-i", ",".join(modules), "--workers=0", "--stop-after-init"])
        if test_enable:
            # TODO: Generate coveragerc
            # cmd.insert(["coverage", "run"])
            cmd.extend(["--test-enable", "--test-tags=/%s" % ",/".join(modules)])
    print(' '.join(cmd))
    subprocess.call(cmd)


def start_ssh():
    if str2bool(os.environ.get("START_SSH")) and is_root():
        subprocess.call("/etc/init.d/ssh start", shell=True)


if __name__ == "__main__":
    start_ssh()
    start_psql()
    start_odoo()
