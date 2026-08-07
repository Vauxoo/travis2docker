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
import logging
import os
import pathlib

from . import __version__
from .exceptions import InvalidRepoBranchError
from .git_run import GitRun
from .travis2docker import Travis2Docker

_logger = logging.getLogger(__name__)


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
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    default_root_path = os.environ.get("TRAVIS2DOCKER_ROOT_PATH")
    if not default_root_path:
        default_root_path = pathlib.Path("~").expanduser()
    default_root_path = str(pathlib.Path(default_root_path) / ".t2d")
    parser = argparse.ArgumentParser(
        prog="travisfile2dockerfile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "travis2docker (t2d) - Generate a development Dockerfile from the\n"
            "deployv image of a repository.\n"
            "\n"
            "Clones the git repository, reads the variables.sh file of the given\n"
            "revision and generates a Dockerfile plus 10-build.sh and 20-run.sh\n"
            "helper scripts to build the image and run a development container."
        ),
        epilog=(
            "examples:\n"
            "  %(prog)s git@github.com:Vauxoo/forecast.git 16.0\n"
            "  %(prog)s git@github.com:Vauxoo/forecast.git pull/42\n"
            "  %(prog)s --docker-image quay.io/vauxoo/proj:tag git@github.com:org/proj.git 16.0\n"
            "  %(prog)s --no-clone --variables-sh-path ./variables.sh foo bar\n"
            "\n"
            "environment variables:\n"
            "  TRAVIS2DOCKER_ROOT_PATH   Override the default root path (~) where\n"
            "                            the .t2d working directory is created.\n"
        ),
    )
    parser.add_argument(
        "git_repo_url",
        help="Git URL of the repository to process. "
        "It is cloned locally to extract the variables.sh file of the deployv image. "
        "For private repositories use the SSH URL (git@...) instead of HTTPS.",
    )
    parser.add_argument(
        "git_revision",
        help="Git revision to process. Accepts a branch name e.g. 'main' or '16.0', "
        "or a pull request with 'pull/#' e.g. 'pull/1'. "
        "NOTE: A sha e.g. b48228 is not supported yet.",
    )
    parser.add_argument(
        "--docker-user",
        dest="docker_user",
        help="Unix user that runs the commands inside the container. "
        "It must exist in the base docker image. "
        "Default: odoo",
    )
    parser.add_argument(
        "--docker-image",
        dest="default_docker_image",
        help="Base docker image for the generated Dockerfile, e.g. the one pushed "
        "by the 'build_docker' pipeline as 'quay.io/vauxoo/PROJECT:TAG'. "
        "Default: built from variables.sh values as 'DOCKER_IMAGE_REPO:MAIN_APP-VERSION-SHA_SHORT'",
    )
    parser.add_argument(
        "--root-path",
        dest="root_path",
        default=default_root_path,
        help="Root directory to store the generated scripts and the cloned repositories. "
        "The 'repo/' and 'script/' sub-directories are created inside it. "
        f"Default: {default_root_path}",
    )
    parser.add_argument(
        "--add-remote",
        dest="remotes",
        help="Comma-separated list of GitHub user/organization names to add as git "
        "remotes in the instance repositories. E.g. 'Vauxoo,moylop260'. "
        "Default: none",
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
        help="Extra arguments appended to the `docker run` command of 20-run.sh. "
        "Note: '-ditP' is always used, no need to add it here. "
        "Default: '-e LANG=C.UTF-8'",
        default="-e LANG=C.UTF-8",
    )
    parser.add_argument(
        "--run-extra-cmds",
        dest="run_extra_cmds",
        nargs="*",
        default="",
        help="Extra commands to run at the end of the 20-run.sh script. "
        "The built image can be referenced with the escaped variable \\$IMAGE. "
        'E.g. "docker rmi -f \\$IMAGE". '
        "Default: none",
    )
    parser.add_argument(
        "--build-extra-args",
        dest="build_extra_args",
        help="Extra arguments appended to the `docker build` command of 10-build.sh. Default: '--rm'",
        default="--rm",
    )
    parser.add_argument(
        "--build-extra-cmds",
        dest="build_extra_cmds",
        nargs="*",
        default="",
        help="Extra commands to run at the end of the 10-build.sh script. "
        "The built image can be referenced with the escaped variable \\$IMAGE. "
        "Default: none",
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
        help="Use a local variables.sh file (or the directory containing it) "
        "instead of extracting it from the cloned repository. "
        "Default: extracted from git_repo_url at git_revision",
    )
    parser.add_argument(
        "--no-clone",
        dest="no_clone",
        action="store_true",
        default=False,
        help="Skip cloning the repository. It requires --variables-sh-path pointing "
        "to a local variables.sh file. "
        "Default: False",
    )
    parser.add_argument(
        "--add-rcfile",
        dest="add_rcfile",
        default="",
        help="Comma-separated list of configuration file paths (e.g. '~/.gitconfig,~/.vimrc') "
        "to copy into the container user's $HOME directory. "
        "Default: none",
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
        help="Environment variable names to enable in the generated Dockerfile. "
        "Each NAME generates an 'ENV NAME=TRUE' line, used to activate optional "
        "installation steps of the image. E.g. '--build-env-args VIM_INSTALL ZSH_INSTALL'. "
        "Default: none",
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
        help="Extra Dockerfile instructions appended at the end of the generated "
        "Dockerfile, each value as a separate line. "
        "Default: none",
    )

    args = parser.parse_args()
    deprecated_args = {
        "--exclude-after-success": args.exclude_after_success,
        "--travis-yml-path": args.travis_yml_path,
        "--runs-at-the-end-script": args.runs_at_the_end_script,
    }
    for deprecated_arg, value in deprecated_args.items():
        if value:
            _logger.warning("%s is deprecated and its value will be ignored", deprecated_arg)
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
    build_env_args = [build_env_arg for build_env_args in args.build_env_args for build_env_arg in build_env_args]
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
        _logger.info("Generated scripts:\n%s", fname_list)
        if not default_docker_image:
            # TODO: Add the URL to open the pipelines
            _logger.info(
                'TIP: Use the parameter "--docker-image=quay.io/vauxoo/PROJECT:TAG" '
                'get the PROJECT:TAG info in your "build_docker" pipeline similar to '
                '\n"... INFO  - deployv.deployv_addon_gitlab_tools.common.common.push_image - '
                'Pushing image ... to quay.io/vauxoo/PROJECT:TAG"'
            )
    else:
        _logger.info("No scripts were generated.")
    if return_result:
        return fname_scripts
