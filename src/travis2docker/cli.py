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
from os.path import expanduser, expandvars, isdir, isfile, join
from sys import stdout

from . import __version__
from .exceptions import InvalidRepoBranchError
from .git_run import GitRun
from .travis2docker import Travis2Docker


def get_git_data(project, path, revision):
    git_obj = GitRun(project, path, path_prefix_repo=True)
    git_obj.update()
    data = {
        'sha': git_obj.get_sha(revision),
        'content': git_obj.show_file('.travis.yml', revision) or git_obj.show_file('.t2d.yml', revision),
        'variables_sh': git_obj.show_file('variables.sh', revision),
        'repo_owner': git_obj.owner,
        'repo_project': git_obj.repo,
        'git_email': git_obj.get_config_data("user.email"),
        'git_user': git_obj.get_config_data("user.name"),
        'revision': revision,
        'project': project,
    }
    return data


def yml_read(yml_path):
    yml_path_expanded = expandvars(expanduser(yml_path))
    alt_yml_path_expanded = None
    if isdir(yml_path_expanded):
        yml_path_expanded = join(yml_path_expanded, '.travis.yml')
        alt_yml_path_expanded = join(yml_path_expanded, '.t2d.yml')
    if not isfile(yml_path_expanded):
        if alt_yml_path_expanded and isfile(alt_yml_path_expanded):
            yml_path_expanded = alt_yml_path_expanded
        else:
            return
    with open(yml_path_expanded, "r") as f_yml:
        return f_yml.read()


def main(return_result=False):
    parser = argparse.ArgumentParser(
        prog='travisfile2dockerfile',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            'travis2docker (t2d) — Generate Dockerfiles from Travis CI configuration.\n'
            '\n'
            'Clones a git repository, reads its .travis.yml (or .t2d.yml) file,\n'
            'and generates a set of Dockerfile and helper scripts that reproduce\n'
            'the Travis CI build environment locally using Docker.'
        ),
        epilog=(
            'examples:\n'
            '  %(prog)s git@github.com:org/repo.git 12.0\n'
            '  %(prog)s git@github.com:org/repo.git pull/42\n'
            '  %(prog)s --no-clone --travis-yml-path ./my.travis.yml . dummy\n'
            '  %(prog)s --deployv --docker-image quay.io/vauxoo/proj:tag git@github.com:org/repo.git 16.0\n'
            '\n'
            'environment variables:\n'
            '  TRAVIS2DOCKER_ROOT_PATH   Override the default root path (~) where\n'
            '                            the .t2d working directory is created.\n'
        ),
    )

    # ── Positional arguments ─────────────────────────────────────────
    parser.add_argument(
        "git_repo_url",
        help=(
            'Git URL of the repository to process.\n'
            'The repo is cloned locally to extract .travis.yml or .t2d.yml.\n'
            'For private repositories use SSH URLs (git@...) instead of HTTPS.'
        ),
    )
    parser.add_argument(
        "git_revision",
        help=(
            'Git revision to build. Accepts:\n'
            '  - Branch name   : master, 14.0, 16.0\n'
            '  - Pull request  : pull/123\n'
            'Note: raw SHA references are not supported yet.'
        ),
    )

    # ── Docker options ───────────────────────────────────────────────
    parser.add_argument(
        '--docker-user',
        dest='docker_user',
        help=(
            'Unix user that will run commands inside the container.\n'
            'Must match a user present in the base Docker image.\n'
            '(default: root)'
        ),
    )
    parser.add_argument(
        '--docker-image',
        dest='default_docker_image',
        help=(
            'Base Docker image for the generated Dockerfile.\n'
            'Only needed when .travis.yml does not specify build_image.\n'
            'NOTE: the current default is a legacy Odoo 8.0 image; you\n'
            'likely want to override it for modern projects.\n'
            '(default: vauxoo/odoo-80-image-shippable-auto)'
        ),
    )

    # ── Paths and files ──────────────────────────────────────────────
    default_root_path = os.environ.get('TRAVIS2DOCKER_ROOT_PATH')
    if not default_root_path:
        default_root_path = os.path.expanduser("~")
    default_root_path = join(default_root_path, '.t2d')
    parser.add_argument(
        '--root-path',
        dest='root_path',
        default=default_root_path,
        help=(
            'Root directory where all generated scripts and cloned repos\n'
            'are stored. Sub-directories "repo/" and "script/" are created\n'
            'inside this path automatically.\n'
            f'(default: {default_root_path})'
        ),
    )
    parser.add_argument(
        '--travis-yml-path',
        dest='travis_yml_path',
        default=None,
        help=(
            'Use a local .travis.yml (or .t2d.yml) file instead of\n'
            'extracting it from the cloned repository.\n'
            'Accepts a file path or a directory containing .travis.yml.\n'
            '(default: extracted from git_repo_url at git_revision)'
        ),
    )
    parser.add_argument(
        '--add-rcfile',
        dest='add_rcfile',
        default="",
        help=(
            'Comma-separated list of configuration file paths (e.g. .pylintrc,\n'
            '.flake8) to copy into the container user\'s $HOME directory.\n'
            'Paths are expanded with ~ notation.\n'
            '(default: none)'
        ),
    )

    # ── Git options ──────────────────────────────────────────────────
    parser.add_argument(
        '--add-remote',
        dest='remotes',
        help=(
            'Comma-separated list of GitHub user/org names to add as git\n'
            'remotes in the build directory.\n'
            'Example: --add-remote Vauxoo,moylop260\n'
            '(default: none)'
        ),
    )
    parser.add_argument(
        '--no-clone',
        dest='no_clone',
        action='store_true',
        default=False,
        help=(
            'Skip cloning the repository. When active, you must also\n'
            'provide --travis-yml-path pointing to a local CI config file.\n'
            'Useful for testing local .travis.yml changes without pushing.\n'
            '(default: False)'
        ),
    )

    # ── Travis CI section control ────────────────────────────────────
    parser.add_argument(
        '--exclude-after-success',
        dest='exclude_after_success',
        action='store_true',
        default=False,
        help=(
            'Exclude the after_success section from the generated\n'
            'entrypoint script. Useful to skip steps like coverage\n'
            'uploads or deployment triggers during local testing.\n'
            '(default: False)'
        ),
    )

    # ── docker run customization ─────────────────────────────────────
    parser.add_argument(
        '--run-extra-args',
        dest='run_extra_args',
        default='-itP -e LANG=C.UTF-8',
        help=(
            'Extra flags appended to the "docker run" command.\n'
            '(default: "-itP -e LANG=C.UTF-8")'
        ),
    )
    parser.add_argument(
        '--run-extra-cmds',
        dest='run_extra_cmds',
        nargs='*',
        default="",
        help=(
            'Commands to execute after the generated "run" script.\n'
            'You can reference the built image via the escaped\n'
            'variable \\$IMAGE.\n'
            'Example: --run-extra-cmds "docker rmi -f \\$IMAGE"\n'
            '(default: none)'
        ),
    )

    # ── docker build customization ───────────────────────────────────
    parser.add_argument(
        '--build-extra-args',
        dest='build_extra_args',
        default='--rm',
        help=(
            'Extra flags appended to the "docker build" command.\n'
            '(default: "--rm")'
        ),
    )
    parser.add_argument(
        '--build-extra-cmds',
        dest='build_extra_cmds',
        nargs='*',
        default="",
        help=(
            'Commands to execute after the generated "build" script.\n'
            'You can reference the built image via the escaped\n'
            'variable \\$IMAGE.\n'
            '(default: none)'
        ),
    )
    parser.add_argument(
        '--build-extra-steps',
        nargs='*',
        default="",
        dest='build_extra_steps',
        help=(
            'Extra Dockerfile instructions appended at the end of\n'
            'the generated Dockerfile. Each value is added as a\n'
            'separate line.\n'
            '(default: none)'
        ),
    )
    parser.add_argument(
        '--build-env-args',
        dest='build_env_args',
        nargs='*',
        action='append',
        default=[],
        help=(
            'Declare build-time environment variables for Docker.\n'
            'Each variable NAME produces these Dockerfile lines:\n'
            '  ARG NAME\n'
            '  ENV NAME=$NAME\n'
            'Can be specified multiple times.\n'
            'Example: --build-env-args MY_VAR\n'
            'NOTE: in DeployV mode, these are rendered differently\n'
            '(as shell exports rather than ARG/ENV pairs).\n'
            'More info: https://vsupalov.com/docker-build-time-env-values\n'
            '(default: none)'
        ),
    )

    # ── Script hooks ─────────────────────────────────────────────────
    parser.add_argument(
        '--runs-at-the-end-script',
        dest='runs_at_the_end_script',
        nargs='*',
        default="",
        help=(
            'Commands appended at the end of the generated "script"\n'
            'entrypoint (after the main Travis script section).\n'
            'You can reference the built image via \\$IMAGE.\n'
            'NOTE: if omitted, "sleep 2" is injected by default to\n'
            'keep the container alive for interactive debugging. Pass\n'
            'an empty string to disable: --runs-at-the-end-script ""\n'
            '(default: "sleep 2")'
        ),
    )

    # ── DeployV mode ─────────────────────────────────────────────────
    parser.add_argument(
        '--deployv',
        dest='deployv',
        action='store_true',
        default=False,
        help=(
            'Enable DeployV mode: use the Docker image built by the CI\n'
            'pipeline instead of building from .travis.yml.\n'
            'If the repo has no .travis.yml but contains a variables.sh,\n'
            'this mode is activated automatically.\n'
            'The image name is auto-constructed from variables.sh as:\n'
            '  DOCKER_IMAGE_REPO:MAIN_APP-VERSION-SHA_SHORT\n'
            '(default: False)'
        ),
    )

    # ── Version ──────────────────────────────────────────────────────
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)

    args = parser.parse_args()
    revision = args.git_revision
    git_repo = args.git_repo_url
    git_base = GitRun.get_data_url(git_repo, False)[0]
    docker_user = args.docker_user
    root_path = args.root_path
    default_docker_image = args.default_docker_image
    remotes = args.remotes and args.remotes.split(',')
    exclude_after_success = args.exclude_after_success
    run_extra_args = args.run_extra_args
    build_extra_args = args.build_extra_args
    travis_yml_path = args.travis_yml_path
    build_extra_cmds = '\n'.join(args.build_extra_cmds)
    run_extra_cmds = '\n'.join(args.run_extra_cmds)
    no_clone = args.no_clone
    deployv = args.deployv
    rcfiles_args = args.add_rcfile and args.add_rcfile.split(',')
    runs_at_the_end_script = args.runs_at_the_end_script or None
    build_env_args = [arg for sublist in args.build_env_args for arg in sublist]
    rcfiles = [(expanduser(rc_file), os.path.join('$HOME', os.path.basename(rc_file))) for rc_file in rcfiles_args]
    if no_clone:
        os_kwargs = {
            'repo_owner': 'local_file',
            'repo_project': 'local_file',
            'revision': revision,
            'sha': 'local_file',
            'project': git_repo,
        }
    else:
        os_kwargs = get_git_data(git_repo, join(root_path, 'repo'), revision)

    if travis_yml_path:
        yml_content = yml_read(travis_yml_path)
    else:
        yml_content = os_kwargs['content']

    if not yml_content and os_kwargs.get("variables_sh"):
        deployv = True
        yml_content = "deployv: True"
    if not default_docker_image and not deployv:
        default_docker_image = 'vauxoo/odoo-80-image-shippable-auto'

    if not yml_content:
        msg = (
            "The file %s is empty." % travis_yml_path
            if travis_yml_path
            else "The repo or the branch is incorrect value, because "
            + "It can not got the .travis.yml or variables.sh content from %s %s. " % (git_repo, revision)
            + "\nPlease, verify access repository,"
            + "\nverify exists url and revision, "
            + "\nverify exists .travis.yml"
        )
        raise InvalidRepoBranchError(msg)
    os_kwargs.update({'remotes': remotes, 'git_base': git_base})
    if docker_user:
        os_kwargs.update({'user': docker_user})
    t2d = Travis2Docker(
        yml_buffer=yml_content,
        work_path=join(root_path, 'script', GitRun.url2dirname(git_repo), revision),
        image=default_docker_image,
        os_kwargs=os_kwargs,
        copy_paths=[(expanduser("~/.ssh"), "$HOME/.ssh")] + rcfiles,
        runs_at_the_end_script=runs_at_the_end_script,
        build_env_args=build_env_args,
        deployv=deployv,
        build_extra_steps=args.build_extra_steps,
    )
    t2d.build_extra_params = {
        'extra_params': build_extra_args,
        'extra_cmds': build_extra_cmds,
    }
    t2d.run_extra_params = {
        'extra_params': run_extra_args,
        'extra_cmds': run_extra_cmds,
    }
    fname_scripts = t2d.compute_dockerfile(skip_after_success=exclude_after_success)
    if fname_scripts:
        fname_list = '- ' + '\n- '.join(fname_scripts)
        stdout.write('\nGenerated scripts:\n%s\n' % fname_list)
        if deployv:
            stdout.write("=" * 80)
            stdout.write(
                '\nUsing --deployv option you will need to run the following extra step '
                'manually after to create the container or after running 20-run.sh script'
            )
            stdout.write(
                '\ndocker exec -it --user=root CONTAINER '
                'find /home/odoo -maxdepth 1 -not -user odoo -exec chown -R odoo:odoo {} \\;\n'
            )
            if not default_docker_image:
                # TODO: Add the URL to open the pipelines
                stdout.write(
                    '\nTIP: Use the parameter "--docker-image=quay.io/vauxoo/PROJECT:TAG" '
                    'get the PROJECT:TAG info in your "build_docker" pipeline similar to '
                    '\n"... INFO  - deployv.deployv_addon_gitlab_tools.common.common.push_image - '
                    'Pushing image ... to quay.io/vauxoo/PROJECT:TAG"\n'
                )
            stdout.write("=" * 80)
    else:
        stdout.write('\nNo scripts were generated.')
    if return_result:
        return fname_scripts
