# No logger planned to use here
# pylint: disable=print-used,consider-using-with

import os
import pathlib
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
        fname_dkr = str(pathlib.Path(script) / "Dockerfile")
        pipe = subprocess.Popen(
            [lint_bin, "-f", fname_dkr],
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
        )
        output = pipe.stdout.read().decode("utf-8")
        assert "Check passed" in output, fname_dkr


def create_repo(base_path, files):
    repo_path = pathlib.Path(base_path) / "myrepo"
    repo_path.mkdir(parents=True)
    subprocess.check_call(["git", "init", "-b", "main", str(repo_path)])
    for fname, content in files.items():
        (repo_path / fname).write_text(content)
    subprocess.check_call(["git", "-C", repo_path, "add", "-A"])
    subprocess.check_call([
        "git",
        "-C",
        repo_path,
        "-c",
        "user.email=test@test.com",
        "-c",
        "user.name=test",
        "commit",
        "-m",
        "initial",
    ])
    # Return the path relative to base_path: an absolute path would be flattened
    # into the clone dirname, exceeding the Windows MAX_PATH limit
    return repo_path.name


def test_main_deployv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = create_repo(tmp_path, {"variables.sh": VARIABLES_SH})
    sys.argv = [
        "travis2docker",
        repo,
        "main",
        "--root-path",
        str(tmp_path / "t2d"),
        "--build-env-args",
        "BUILD_ENV1",
        "--build-env-args",
        "BUILD_ENV2",
        "--build-extra-steps",
        "touch /home/odoo/extra_step_done",
        # Deprecated parameters must still be accepted (and ignored)
        "--deployv",
        "--exclude-after-success",
        "--travis-yml-path",
        "foo.yml",
        "--runs-at-the-end-script",
        "echo done",
    ]
    scripts = cli_main(return_result=True)
    assert len(scripts) == 1, "Scripts returned should be 1"
    dkr_content = (pathlib.Path(scripts[0]) / "Dockerfile").read_text()
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
        script_path = pathlib.Path(scripts[0]) / script
        assert script_path.is_file()
        assert os.access(script_path, os.X_OK), "%s should be executable" % script
    check_dockerfile_lint(scripts)


def test_main_docker_image_parameter(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = create_repo(tmp_path, {"variables.sh": VARIABLES_SH})
    sys.argv = [
        "travis2docker",
        repo,
        "main",
        "--root-path",
        str(tmp_path / "t2d"),
        "--docker-image",
        "quay.io/vauxoo/myproject:custom-tag",
    ]
    scripts = cli_main(return_result=True)
    assert len(scripts) == 1, "Scripts returned should be 1"
    dkr_content = (pathlib.Path(scripts[0]) / "Dockerfile").read_text()
    assert "FROM quay.io/vauxoo/myproject:custom-tag" in dkr_content


def test_main_no_clone(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "variables.sh").write_text(VARIABLES_SH)
    sys.argv = [
        "travis2docker",
        "foo",
        "bar",
        "--no-clone",
        "--variables-sh-path",
        str(tmp_path),
        "--root-path",
        str(tmp_path / "t2d"),
    ]
    scripts = cli_main(return_result=True)
    assert len(scripts) == 1, "Scripts returned should be 1"
    dkr_content = (pathlib.Path(scripts[0]) / "Dockerfile").read_text()
    assert "FROM quay.io/vauxoo/myproject:myproject-16.0-local_f" in dkr_content


def test_main_no_clone_missing_variables_sh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sys.argv = [
        "travis2docker",
        "foo",
        "bar",
        "--no-clone",
        "--variables-sh-path",
        str(tmp_path / "missing.sh"),
        "--root-path",
        str(tmp_path / "t2d"),
    ]
    with pytest.raises(InvalidRepoBranchError):
        cli_main(return_result=True)


def test_main_without_variables_sh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = create_repo(tmp_path, {"README.md": "no variables.sh here"})
    sys.argv = [
        "travis2docker",
        repo,
        "main",
        "--root-path",
        str(tmp_path / "t2d"),
    ]
    with pytest.raises(InvalidRepoBranchError):
        cli_main(return_result=True)
