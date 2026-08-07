"""Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -mtravis2docker` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``travis2docker.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``travis2docker.__main__`` in ``sys.modules``.

"""

import argparse
import os
import pathlib
from sys import stdout

from . import __version__
from .exceptions import InvalidRepoBranchError
from .git_run import GitRun
from .travis2docker import Travis2Docker


def variables_sh_read(variables_sh_path):
    variables_sh_path = pathlib.Path(variables_sh_path).expanduser()
    if variables_sh_path.is_dir():
        variables_sh_path /= "variables.sh"
    if not variables_sh_path.is_file():
        return None
    return variables_sh_path.read_text()


def get_git_data(project, path, revision):
    git_obj = GitRun(project, path, path_prefix_repo=True)
    git_obj.update()
    data = {
        "sha": git_obj.get_sha(revision),
        "variables_sh": git_obj.show_file("variables.sh", revision),
        "repo_owner": git_obj.owner,
        "repo_project": git_obj.repo,
        "git_email": git_obj.get_config_data("user.email"),
        "git_user": git_obj.get_config_data("user.name"),
        "revision": revision,
        "project": project,
    }
    return data


def main(return_result=False):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "git_repo_url",
        help="Specify repository git of work."
        "\nThis is used to clone it "
        "and get the variables.sh file of the deployv image"
        "\nIf your repository is private, "
        "don't use https url, "
        "use ssh url",
    )
    parser.add_argument(
        "git_revision",
        help="Revision git of work."
        "\nYou can use "
        "branch name e.g. master or 8.0 "
        "or pull number with 'pull/#' e.g. pull/1 "
        "NOTE: A sha e.g. b48228 NOT IMPLEMENTED YET",
    )
    parser.add_argument(
        "--docker-user",
        dest="docker_user",
        help="User of work into Dockerfile.\nBased on your docker image.\nDefault: odoo",
    )
    parser.add_argument(
        "--docker-image",
        dest="default_docker_image",
        help="Docker image to use by default in Dockerfile."
        "\nDefault: built from variables.sh as "
        "'DOCKER_IMAGE_REPO:MAIN_APP-VERSION-SHA_SHORT'",
    )
    default_root_path = os.environ.get("TRAVIS2DOCKER_ROOT_PATH")
    if not default_root_path:
        default_root_path = pathlib.Path("~").expanduser()
    default_root_path = str(pathlib.Path(default_root_path) / ".t2d")
    parser.add_argument(
        "--root-path",
        dest="root_path",
        help=f"Root path to save scripts generated.\nDefault: {default_root_path}",
        default=default_root_path,
    )
    parser.add_argument(
        "--add-remote",
        dest="remotes",
        help="Add git remote to git of build path, separated by a comma.\nUse remote name. E.g. 'Vauxoo,moylop260'",
    )
    parser.add_argument(
        "--exclude-after-success",
        dest="exclude_after_success",
        action="store_true",
        default=False,
        help="Deprecated. Ignored: the travis_after_success section does not exist anymore",
    )
    parser.add_argument(
        "--run-extra-args",
        dest="run_extra_args",
        help="Extra arguments to `docker run RUN_EXTRA_ARGS` command",
        default="-itP -e LANG=C.UTF-8",
    )
    parser.add_argument(
        "--run-extra-cmds",
        dest="run_extra_cmds",
        nargs="*",
        default="",
        help='Extra commands to run after "run" script. '
        "Note: You can use \\$IMAGE escaped environment variable."
        'E.g. "docker rmi -f \\$IMAGE"',
    )
    parser.add_argument(
        "--build-extra-args",
        dest="build_extra_args",
        help="Extra arguments to `docker build BUILD_EXTRA_ARGS` command",
        default="--rm",
    )
    parser.add_argument(
        "--build-extra-cmds",
        dest="build_extra_cmds",
        nargs="*",
        default="",
        help='Extra commands to run after "build" script. Note: You can use \\$IMAGE escaped environment variable.',
    )
    parser.add_argument(
        "--travis-yml-path",
        dest="travis_yml_path",
        default=None,
        help="Deprecated. Ignored: the .travis.yml file is not used anymore",
    )
    parser.add_argument(
        "--variables-sh-path",
        dest="variables_sh_path",
        default=None,
        help="Optional path of the variables.sh file (or the directory containing it) to use.\n"
        "Default: Extracted from git repo and git revision.",
    )
    parser.add_argument(
        "--no-clone",
        dest="no_clone",
        action="store_true",
        default=False,
        help="Avoid cloning the repository. It requires --variables-sh-path",
    )
    parser.add_argument(
        "--add-rcfile",
        dest="add_rcfile",
        default="",
        help="Optional paths of configuration files to "
        "copy for user's HOME path into container, separated by a comma.",
    )
    parser.add_argument("-v", "--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument(
        "--runs-at-the-end-script",
        dest="runs_at_the_end_script",
        nargs="*",
        default="",
        help="Deprecated. Ignored: the script section of .travis.yml does not exist anymore",
    )
    parser.add_argument(
        "--build-env-args",
        dest="build_env_args",
        nargs="*",
        action="append",
        default=[],
        help="Args used as environment variables "
        "More info about: https://vsupalov.com/docker-build-time-env-values\n"
        "E.g. --build-env-args ENVAR1\n"
        "It generates the following line for Dockerfile:\n"
        "ARG ENVVAR1\nENV ENVVAR1=$ENVVAR1",
    )
    parser.add_argument(
        "--deployv",
        dest="deployv",
        action="store_true",
        default=True,
        help="Deprecated. The deployv image is now the only supported mode",
    )
    parser.add_argument(
        "--build-extra-steps",
        nargs="*",
        default="",
        dest="build_extra_steps",
        help="Append these extra steps at the end of the Dockerfile",
    )

    args = parser.parse_args()
    deprecated_args = {
        "--exclude-after-success": args.exclude_after_success,
        "--travis-yml-path": args.travis_yml_path,
        "--runs-at-the-end-script": args.runs_at_the_end_script,
    }
    for deprecated_arg, value in deprecated_args.items():
        if value:
            stdout.write("WARNING: %s is deprecated and its value will be ignored\n" % deprecated_arg)
    revision = args.git_revision
    git_repo = args.git_repo_url
    git_base = GitRun.get_data_url(git_repo, False)[0]
    docker_user = args.docker_user
    root_path = args.root_path
    default_docker_image = args.default_docker_image
    remotes = args.remotes and args.remotes.split(",")
    run_extra_args = args.run_extra_args
    build_extra_args = args.build_extra_args
    build_extra_cmds = "\n".join(args.build_extra_cmds)
    run_extra_cmds = "\n".join(args.run_extra_cmds)
    rcfiles_args = args.add_rcfile and args.add_rcfile.split(",")
    build_env_args = [build_env_args[0] for build_env_args in args.build_env_args]
    rcfiles = [
        (pathlib.Path(rc_file).expanduser(), "$HOME/%s" % pathlib.Path(rc_file).name) for rc_file in rcfiles_args
    ]
    if args.no_clone:
        os_kwargs = {
            "repo_owner": "local_file",
            "repo_project": "local_file",
            "revision": revision,
            "sha": "local_file",
            "project": git_repo,
        }
    else:
        os_kwargs = get_git_data(git_repo, pathlib.Path(root_path) / "repo", revision)

    if args.variables_sh_path:
        os_kwargs["variables_sh"] = variables_sh_read(args.variables_sh_path)

    if not os_kwargs.get("variables_sh"):
        msg = (
            "The file %s is empty or does not exist." % args.variables_sh_path
            if args.variables_sh_path
            else "The repo or the branch is incorrect value, because "
            + "It can not got the variables.sh content from %s %s. " % (git_repo, revision)
            + "\nPlease, verify access repository,"
            + "\nverify exists url and revision, "
            + "\nverify exists variables.sh"
        )
        raise InvalidRepoBranchError(msg)
    os_kwargs.update({"remotes": remotes, "git_base": git_base})
    if docker_user:
        os_kwargs.update({"user": docker_user})
    t2d = Travis2Docker(
        work_path=pathlib.Path(root_path) / "script" / GitRun.url2dirname(git_repo) / revision,
        image=default_docker_image,
        os_kwargs=os_kwargs,
        copy_paths=[(pathlib.Path("~/.ssh").expanduser(), "$HOME/.ssh")] + rcfiles,
        build_env_args=build_env_args,
        build_extra_steps=args.build_extra_steps,
    )
    t2d.build_extra_params = {
        "extra_params": build_extra_args,
        "extra_cmds": build_extra_cmds,
    }
    t2d.run_extra_params = {
        "extra_params": run_extra_args,
        "extra_cmds": run_extra_cmds,
    }
    fname_scripts = t2d.compute_dockerfile()
    if fname_scripts:
        fname_list = "- " + "\n- ".join(fname_scripts)
        stdout.write("\nGenerated scripts:\n%s\n" % fname_list)
        if not default_docker_image:
            stdout.write("=" * 80)
            # TODO: Add the URL to open the pipelines
            stdout.write(
                '\nTIP: Use the parameter "--docker-image=quay.io/vauxoo/PROJECT:TAG" '
                'get the PROJECT:TAG info in your "build_docker" pipeline similar to '
                '\n"... INFO  - deployv.deployv_addon_gitlab_tools.common.common.push_image - '
                'Pushing image ... to quay.io/vauxoo/PROJECT:TAG"\n'
            )
            stdout.write("=" * 80)
    else:
        stdout.write("\nNo scripts were generated.")
    if return_result:
        return fname_scripts
