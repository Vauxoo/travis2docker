# No logger planned to use here
# pylint: disable=print-used,consider-using-with

import os
import subprocess
import sys
from shutil import which

import pytest

from travis2docker.cli import main as cli_main
from travis2docker.exceptions import InvalidRepoBranchError

VARIABLES_SH = """export DOCKER_IMAGE_REPO=quay.io/vauxoo/myproject
export MAIN_APP=myproject
export VERSION=16.0
export CUSTOM_VAR="custom value"
"""


def check_dockerfile_lint(scripts):
    npm_bin = which("npm")
    npm_bin_path = subprocess.check_output([npm_bin, "list"]).decode("UTF-8").strip("\n") if npm_bin else ""
    npm_bin_path_g = subprocess.check_output([npm_bin, "list", "-g"]).decode("UTF-8").strip("\n") if npm_bin else ""
    lint_bin_name = "dockerfile_lint"
    lint_bin = which(lint_bin_name) or which(lint_bin_name, path=npm_bin_path + os.pathsep + npm_bin_path_g)
    assert lint_bin, "'%s' not found." % lint_bin_name
    for script in scripts:
        fname_dkr = os.path.join(script, "Dockerfile")
        pipe = subprocess.Popen(
            [lint_bin, "-f", fname_dkr],
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
        )
        output = pipe.stdout.read().decode("utf-8")
        assert "Check passed" in output, fname_dkr
        print("Check dockerfile output", output)


def create_repo(base_path, files):
    repo_path = os.path.join(str(base_path), "myrepo")
    os.makedirs(repo_path)
    subprocess.check_call(["git", "init", "-b", "main", repo_path])
    for fname, content in files.items():
        with open(os.path.join(repo_path, fname), "w") as f_repo:
            f_repo.write(content)
    subprocess.check_call(["git", "-C", repo_path, "add", "-A"])
    subprocess.check_call(
        ["git", "-C", repo_path, "-c", "user.email=test@test.com", "-c", "user.name=test", "commit", "-m", "initial"]
    )
    return repo_path


def test_main_deployv(tmp_path):
    repo = create_repo(tmp_path, {"variables.sh": VARIABLES_SH})
    sys.argv = [
        "travis2docker",
        repo,
        "main",
        "--root-path",
        os.path.join(str(tmp_path), "t2d"),
        "--build-env-args",
        "BUILD_ENV1",
        "--build-env-args",
        "BUILD_ENV2",
        "--build-extra-steps",
        "touch /home/odoo/extra_step_done",
    ]
    scripts = cli_main(return_result=True)
    assert len(scripts) == 1, "Scripts returned should be 1"
    fname_dkr = os.path.join(scripts[0], "Dockerfile")
    with open(fname_dkr) as f_dkr:
        dkr_content = f_dkr.read()
    sha_short = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"]).decode("UTF-8")[:7]
    assert "FROM quay.io/vauxoo/myproject:myproject-16.0-%s" % sha_short in dkr_content
    assert "ENV BUILD_ENV1=TRUE" in dkr_content
    assert "ENV BUILD_ENV2=TRUE" in dkr_content
    assert "RUN touch /home/odoo/extra_step_done" in dkr_content
    assert "ENTRYPOINT /entrypoint.sh" in dkr_content
    assert "COPY build.sh /home/odoo/build.sh" in dkr_content
    assert "COPY entrypoint_deployv.sh /entrypoint.sh" in dkr_content
    assert "COPY docker_helper /home/odoo/build" in dkr_content
    for script in ("10-build.sh", "20-run.sh"):
        script_path = os.path.join(scripts[0], script)
        assert os.path.isfile(script_path)
        assert os.access(script_path, os.X_OK), "%s should be executable" % script
    check_dockerfile_lint(scripts)


def test_main_docker_image_parameter(tmp_path):
    repo = create_repo(tmp_path, {"variables.sh": VARIABLES_SH})
    sys.argv = [
        "travis2docker",
        repo,
        "main",
        "--root-path",
        os.path.join(str(tmp_path), "t2d"),
        "--docker-image",
        "quay.io/vauxoo/myproject:custom-tag",
    ]
    scripts = cli_main(return_result=True)
    assert len(scripts) == 1, "Scripts returned should be 1"
    with open(os.path.join(scripts[0], "Dockerfile")) as f_dkr:
        dkr_content = f_dkr.read()
    assert "FROM quay.io/vauxoo/myproject:custom-tag" in dkr_content


def test_main_without_variables_sh(tmp_path):
    repo = create_repo(tmp_path, {"README.md": "no variables.sh here"})
    sys.argv = [
        "travis2docker",
        repo,
        "main",
        "--root-path",
        os.path.join(str(tmp_path), "t2d"),
    ]
    with pytest.raises(InvalidRepoBranchError):
        cli_main(return_result=True)
