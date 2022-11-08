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
    if isdir(yml_path_expanded):
        yml_path_expanded = join(yml_path_expanded, '.travis.yml')
        alt_yml_path_expanded = join(yml_path_expanded, '.t2d.yml')
    if not isfile(yml_path_expanded):
        if isfile(alt_yml_path_expanded):
            yml_path_expanded = alt_yml_path_expanded
        else:
            return
    with open(yml_path_expanded, "r") as f_yml:
        return f_yml.read()


def main(return_result=False):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "git_repo_url",
        help="Specify repository git of work."
        "\nThis is used to clone it "
        "and get file .travis.yml or .shippable.yml"
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
        '--docker-user',
        dest='docker_user',
        help="User of work into Dockerfile." "\nBased on your docker image." "\nDefault: root",
    )
    parser.add_argument(
        '--docker-image',
        dest='default_docker_image',
        help="Docker image to use by default in Dockerfile."
        "\nUse this parameter if don't "
        "exists value: 'build_image: IMAGE_NAME' "
        "in .travis.yml"
        "\nDefault: 'vauxoo/odoo-80-image-shippable-auto'",
    )
    default_root_path = os.environ.get('TRAVIS2DOCKER_ROOT_PATH')
    if not default_root_path:
        default_root_path = os.path.expanduser("~")
    default_root_path = join(default_root_path, '.t2d')
    parser.add_argument(
        '--root-path',
        dest='root_path',
        help="Root path to save scripts generated." "\nDefault: 'tmp' dir of your O.S.",
        default=default_root_path,
    )
    parser.add_argument(
        '--add-remote',
        dest='remotes',
        help='Add git remote to git of build path, separated by a comma.' "\nUse remote name. E.g. 'Vauxoo,moylop260'",
    )
    parser.add_argument(
        '--exclude-after-success',
        dest='exclude_after_success',
        action='store_true',
        default=False,
        help='Exclude `travis_after_success` section to entrypoint',
    )
    parser.add_argument(
        '--run-extra-args',
        dest='run_extra_args',
        help="Extra arguments to `docker run RUN_EXTRA_ARGS` command",
        default='-itP -e LANG=C.UTF-8',
    )
    parser.add_argument(
        '--run-extra-cmds',
        dest='run_extra_cmds',
        nargs='*',
        default="",
        help='Extra commands to run after "run" script. '
        'Note: You can use \\$IMAGE escaped environment variable.'
        'E.g. "docker rmi -f \\$IMAGE"',
    )
    parser.add_argument(
        '--build-extra-args',
        dest='build_extra_args',
        help="Extra arguments to `docker build BUILD_EXTRA_ARGS` command",
        default='--rm',
    )
    parser.add_argument(
        '--build-extra-cmds',
        dest='build_extra_cmds',
        nargs='*',
        default="",
        help='Extra commands to run after "build" script. ' 'Note: You can use \\$IMAGE escaped environment variable.',
    )
    parser.add_argument(
        '--travis-yml-path',
        dest='travis_yml_path',
        help="Optional path of file .travis.yml to use.\n" "Default: Extracted from git repo and git revision.",
        default=None,
    )
    parser.add_argument(
        '--no-clone',
        dest='no_clone',
        action='store_true',
        help="Avoid clone the repository. It will require travis-yml-path",
        default=False,
    )
    parser.add_argument(
        '--add-rcfile',
        dest='add_rcfile',
        default="",
        help='Optional paths of configuration files to '
        'copy for user\'s HOME path into container, separated by a comma.',
    )
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    parser.add_argument(
        '--runs-at-the-end-script',
        dest='runs_at_the_end_script',
        nargs='*',
        default="",
        help='Extra commands to run after "script" file. ' 'Note: You can use \\$IMAGE escaped environment variable.',
    )
    parser.add_argument(
        '--build-env-args',
        dest='build_env_args',
        nargs='*',
        action='append',
        default=[],
        help='Args used as environment variables '
        'More info about: https://vsupalov.com/docker-build-time-env-values\n'
        'E.g. --build-env-args ENVAR1\n'
        'It generates the following line for Dockerfile:\n'
        'ARG ENVVAR1\nENV ENVVAR1=$ENVVAR1',
    )
    parser.add_argument(
        '--deployv',
        dest='deployv',
        action='store_true',
        default=False,
        help='Use the image generated from the CI and used in deployV',
    )

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
    build_env_args = [build_env_args[0] for build_env_args in args.build_env_args]
    rcfiles = [(expanduser(rc_file), os.path.join('$HOME', os.path.basename(rc_file))) for rc_file in rcfiles_args]
    if not default_docker_image and not deployv:
        default_docker_image = 'vauxoo/odoo-80-image-shippable-auto'
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
    if not yml_content:
        msg = (
            "The file %s is empty." % (travis_yml_path)
            if travis_yml_path
            else "The repo or the branch is incorrect value, because "
            + "It can not got the .travis.yml or variables.sh content from %s %s. " % (git_repo, revision)
            + "\nPlease, verify access repository,"
            + "\nverify exists url and revision, "
            + "\nverify exists .travis.yml"
        )
        raise InvalidRepoBranchError(msg)
    os_kwargs.update({'add_self_rsa_pub': True, 'remotes': remotes, 'git_base': git_base})
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
