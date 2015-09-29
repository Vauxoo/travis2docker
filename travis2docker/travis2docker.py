#!/usr/bin/python
# -*- coding: utf-8 -*-
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#
#    Copyright (c) 2013 Vauxoo - http://www.vauxoo.com/
#    All Rights Reserved.
#    info Vauxoo (info@vauxoo.com)
############################################################################
#    Coded by: moylop260 (moylop260@vauxoo.com)
############################################################################
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import argparse
import itertools
import os
import re
import shutil
import stat
import types
from sys import stdout
from tempfile import gettempdir

import yaml
from git_run import GitRun


# TODO: Change name of class and variables to cmd
class travis(object):

    def load_travis_file(self, branch):
        self.git_obj.update()
        yaml_loaded = None
        for fname in ['.travis.yml', '.shippable.yml']:
            yaml_str = self.git_obj.show_file(fname, branch)
            try:
                yaml_loaded = yaml.load(yaml_str)
                break
            except AttributeError:
                pass
        return yaml_loaded

    def get_folder_name(self, name):
        for invalid_char in '@:/#':
            name = name.replace(invalid_char, '_')
        return name

    def get_repo_path(self, root_path):
        name = self.get_folder_name(self.git_project)
        repo_path = os.path.join(root_path, 'repo', name)
        return repo_path

    def get_script_path(self, root_path):
        name = self.get_folder_name(self.git_project)
        script_path = os.path.join(
            root_path, 'script',
            name, self.get_folder_name(self.revision), self.sha)
        return script_path

    def __init__(self, git_project, revision,
                 command_format='docker', docker_user=None,
                 root_path=None, default_docker_image=None):
        """
        Method Constructor
        @fname_dockerfile: str name of file dockerfile to save.
        @format_cmd: str name of format of command.
                     bash: Make a bash script.
                     docker: Make a dockerfile script.
        """
        if root_path is None:
            self.root_path = os.path.join(
                gettempdir(),
                os.path.splitext(os.path.basename(__file__))[0],
            )
        else:
            self.root_path = os.path.expandvars(
                os.path.expanduser(root_path)
            )
        self.default_docker_image = default_docker_image
        self.git_project = git_project
        self.revision = revision
        git_path = self.get_repo_path(self.root_path)
        self.git_obj = GitRun(git_project, git_path)
        self.travis_data = self.load_travis_file(revision)
        self.sha = self.git_obj.get_sha(revision)
        if not self.travis_data:
            raise Exception(
                "Make sure you have access to repository"
                " " + git_project + " and that the file .travis.yml"
                " exists in branch or revision " + revision
            )
        self.travis2docker_section = [
            # ('build_image', 'build_image'),
            ('python', 'python'),
            ('env', 'env'),
            ('install', 'run'),
            ('script', 'script'),
        ]
        self.travis2docker_section_dict = dict(self.travis2docker_section)
        self.scripts_root_path = self.get_script_path(self.root_path)
        env_regex_str = r"(?P<var>[\w]*)[ ]*[\=][ ]*[\"\']{0,1}" + \
            r"(?P<value>[\w\.\-\_/\$\{\}\:,]*)[\"\']{0,1}"
        export_regex_str = r"(?P<export>export|EXPORT)( )+" + env_regex_str
        self.env_regex = re.compile(env_regex_str, re.M)
        self.export_regex = re.compile(export_regex_str, re.M)
        self.extra_env_from_run = ""
        self.command_format = command_format
        self.docker_user = docker_user or 'root'

    # def get_travis_type(self, repo_git):
    #     self.repo_git_type = None
    #     if os.path.isdir(repo_git):
    #         self.repo_git_type = 'localpath'
    #     elif os.path.isfile(repo_git):
    #         self.repo_git_type = 'file'
    #     else:
    #         regex = r"(?P<host>(git@|https://)([\w\.@]+)(/|:))" \
    #                  r"(?P<owner>[~\w,\-,\_]+)/" \
    #                  r"(?P<repo>[\w,\-,\_]+)(.git){0,1}((/){0,1})"
    #         match_object = re.search(regex, repo_git)
    #         if match_object:
    #             self.repo_git_type = 'remote'

    # def get_travis_data(self, repo_git, branch=None):
    #     self.get_travis_type(repo_git)
    #     if self.repo_git_type == 'remote':
    #         if branch is None:
    #             raise "You need specify branch name with remote repository"
    #         "git show 8.0:.travis.yml"

    def get_travis_section(self, section, *args, **kwards):
        section_type = self.travis2docker_section_dict.get(section, False)
        if not section_type:
            return None
        section_data = self.travis_data.get(section, "")
        if isinstance(section_data, basestring):
            section_data = [section_data]
        job_method = getattr(self, 'get_travis2docker_' + section_type)
        return job_method(section_data, *args, **kwards)

    def get_travis2docker_run(self, section_data,
                              custom_command_format=None,
                              add_extra_env=True):
        if custom_command_format is None:
            custom_command_format = self.command_format
        docker_run = ''
        for line in section_data:
            export_regex_findall = self.export_regex.findall(line)
            for dummy, dummy, var, value in export_regex_findall:
                self.extra_env_from_run += "%s=%s " % (var, value)
            extra_env = add_extra_env and self.extra_env_from_run or ''
            if not export_regex_findall:
                if custom_command_format == 'bash':
                    docker_run += '\n' + extra_env + line
                elif custom_command_format == 'docker':
                    docker_run += '\nRUN ' + extra_env + line
        return docker_run

    def scape_bash_command(self, command):
        return command.replace('$', '\\$').replace('_', '\\_')

    def get_travis2docker_script(self, section_data):
        cmd_str = self.get_travis2docker_run(
            section_data, custom_command_format='bash',
            add_extra_env=False)
        if self.docker_user == 'root':
            sudo_prefix = ''
        else:
            sudo_prefix = 'sudo'
        if self.command_format == 'docker' and cmd_str:
            cmd_str = self.extra_env_from_run + cmd_str
            cmd_str = self.scape_bash_command(cmd_str)
            cmd_str = '\\\\n'.join(cmd_str.strip('\n').split('\n'))
            cmd_str = 'RUN echo """%s"""' % (cmd_str,) \
                + ' | ' + sudo_prefix + 'tee -a /entrypoint.sh \\' + \
                '\n    && ' + sudo_prefix + \
                ' chown %s:%s /entrypoint.sh \\' % (
                    self.docker_user, self.docker_user) + \
                '\n    && ' + sudo_prefix + ' chmod +x /entrypoint.sh'
            cmd_str += '\nENTRYPOINT /entrypoint.sh'
        return cmd_str

    def get_travis2docker_env(self, section_data):
        global_data_cmd = []
        matrix_data_cmd = []
        if 'global' in section_data:
            global_data = section_data.pop('global')
            global_data_cmd = [
                global_env
                for global_env
                in self.get_travis2docker_env(global_data)
            ]
        if 'matrix' in section_data:
            matrix_data = section_data.pop('matrix')
            matrix_data_cmd = [
                matrix_env
                for matrix_env
                in self.get_travis2docker_env(matrix_data)
            ]
        for combination in itertools.product(global_data_cmd, matrix_data_cmd):
            command_str = '\n'.join(combination) + "\n"
            yield command_str

        for line in section_data:
            if line in ['global', 'matrix']:
                continue
            if not isinstance(line, str):
                continue
            docker_env = ""
            for var, value in self.env_regex.findall(line):
                if self.command_format == 'bash':
                    docker_env += "\nexport %s=%s" % (var, value)
                elif self.command_format == 'docker':
                    docker_env += "\nENV %s=%s" % (var, value)
            yield docker_env

    def get_travis2docker_python(self, section_data):
        for line in section_data:
            yield "\n# TODO: Use python version: " + line

    def get_default_cmd(self, dockerfile_path):
        home_user_path = self.docker_user == 'root' and "/root" \
            or os.path.join("/home", self.docker_user)
        project, branch = self.git_project, self.revision
        travis_build_dir = os.path.join(
            home_user_path, "build",
            self.git_obj.owner, self.git_obj.repo,
        )
        if self.command_format == 'bash':
            cmd = "\nsudo su - " + self.docker_user + \
                  "\nsudo chown -R %s:%s %s" % (self.docker_user, self.docker_user, home_user_path) + \
                  "\nexport TRAVIS_BUILD_DIR=%s" % (travis_build_dir) + \
                  "\ngit clone --single-branch %s -b %s " % (project, branch) + \
                  "${TRAVIS_BUILD_DIR}" + \
                  "\n"
        elif self.command_format == 'docker':
            dkr_files_path = os.path.join(dockerfile_path, "files")
            if not os.path.exists(dkr_files_path):
                os.makedirs(dkr_files_path)
            if not os.path.exists(os.path.join(dkr_files_path, 'ssh')):
                shutil.copytree(
                    os.path.expanduser("~/.ssh"),
                    os.path.join(dkr_files_path, 'ssh')
                )
            cmd_refs = 'pull' in self.revision and \
                '+refs/%s/head:refs/%s' % (
                    self.revision, self.revision) or \
                '+refs/heads/%s:refs/heads/%s' % (
                    self.revision, self.revision)

            # TODO: Use sha
            cmd_git_clone = [
                "git init ${TRAVIS_BUILD_DIR}",
                "cd ${TRAVIS_BUILD_DIR}",
                "git remote add origin " + project,
                "git fetch --update-head-ok -p origin %s" % (cmd_refs),
                "git reset --hard " + self.revision,

            ]
            git_user_email = self.git_obj.get_config_data("user.email")
            if git_user_email:
                cmd_git_clone.append(
                    "git config --global user.email \"%s\"" % (git_user_email)
                )
            else:
                cmd_git_clone.append(
                    "git config --unset --global user.email"
                )
            git_user_name = self.git_obj.get_config_data("user.name")
            if git_user_name:
                cmd_git_clone.append(
                    "git config --global user.name \"%s\"" % (git_user_name)
                )
            else:
                cmd_git_clone.append(
                    "git config --unset --global user.name"
                )
            if self.docker_user == 'root':
                sudo_prefix = ''
            else:
                sudo_prefix = 'sudo'
            cmd = 'FROM ' + (self.travis_data.get('build_image', False) or
                             self.default_docker_image) + \
                  '\nUSER ' + self.docker_user + \
                  '\nADD ' + os.path.join("files", 'ssh') + ' ' + \
                  os.path.join(home_user_path, '.ssh') + \
                  "\nENV TRAVIS_BUILD_DIR=%s" % (travis_build_dir) + \
                  "\nWORKDIR ${TRAVIS_BUILD_DIR}" + \
                  "\nRUN %s chown -R %s:%s %s" % (
                      sudo_prefix, self.docker_user,
                      self.docker_user, home_user_path) + \
                  "\nRUN " + ' \\\n    && '.join(cmd_git_clone) + \
                  "\n"
        return cmd

    def get_travis2docker_iter(self):
        travis2docker_cmd_static_str = ""
        travis2docker_cmd_iter_list = []
        for travis_section, dummy in self.travis2docker_section:
            travis2docker_section = self.get_travis_section(travis_section)
            if isinstance(travis2docker_section, types.GeneratorType):
                travis2docker_cmd_iter_list.append([
                    item_iter for item_iter in travis2docker_section
                ])
            elif isinstance(travis2docker_section, basestring):
                travis2docker_cmd_static_str += travis2docker_section + "\n"
        for combination in itertools.product(*travis2docker_cmd_iter_list):
            command_str = '\n'.join(combination) + "\n" + \
                travis2docker_cmd_static_str
            yield command_str

    def get_travis2docker(self):
        count = 1
        fname_scripts = []
        for cmd in self.get_travis2docker_iter():
            fname = os.path.join(
                self.scripts_root_path,
                str(count)
            )
            fname_build = None
            fname_run = None
            if not os.path.exists(fname):
                os.makedirs(fname)
            if self.command_format == 'bash':
                fname = os.path.join(fname, 'script.sh')
                cmd = self.get_default_cmd(os.path.dirname(fname)) + cmd
            elif self.command_format == 'docker':
                fname = os.path.join(fname, 'Dockerfile')
                cmd = self.get_default_cmd(os.path.dirname(fname)) + cmd
                fname_build = os.path.join(
                    os.path.dirname(fname), '10-build.sh'
                )
                fname_run = os.path.join(
                    os.path.dirname(fname), '20-run.sh'
                )
                image_name = self.git_obj.owner + '-' + \
                    self.git_obj.repo + \
                    ":" + self.get_folder_name(self.revision) + \
                    "_" + str(count)
                image_name = image_name.lower()
            else:
                raise Exception(
                    "No command format found %s" % (self.command_format)
                )
            with open(fname, "w") as fdockerfile:
                fdockerfile.write(cmd)

            if fname_build:
                with open(fname_build, "w") as fbuild:
                    fbuild.write(
                        "docker build $1 -t %s %s" % (
                            image_name,
                            os.path.dirname(fname)
                        )
                    )
                st = os.stat(fname_build)
                os.chmod(fname_build, st.st_mode | stat.S_IEXEC)
            if fname_run:
                with open(fname_run, "w") as fbuild:
                    fbuild.write(
                        "docker run $1 -itP %s $2" % (
                            image_name
                        )
                    )
                st = os.stat(fname_run)
                os.chmod(fname_run, st.st_mode | stat.S_IEXEC)
            if self.command_format == 'bash':
                st = os.stat(fname)
                os.chmod(fname, st.st_mode | stat.S_IEXEC)
            count += 1
            fname_scripts.append(os.path.dirname(fname))
        return fname_scripts


def main():
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
        '--docker-user', dest='docker_user',
        help="User of work into Dockerfile."
             "\nBased on your docker image."
             "\nDefault: root",
        default='root'
    )
    parser.add_argument(
        '--docker-image', dest='default_docker_image',
        help="Docker image to use by default in Dockerfile."
             "\nUse this parameter if don't "
             "exists value: 'build_image: IMAGE_NAME' "
             "in .travis.yml"
             "\nDefault: 'vauxoo/odoo-80-image-shippable-auto'",
        default='vauxoo/odoo-80-image-shippable-auto'
    )
    parser.add_argument(
        '--root-path', dest='root_path',
        help="Root path to save scripts generated."
             "\nDefault: 'tmp' dir of your O.S.",
        default=None,
    )
    args = parser.parse_args()
    sha = args.git_revision
    git_repo = args.git_repo_url
    docker_user = args.docker_user
    root_path = args.root_path
    default_docker_image = args.default_docker_image
    travis_obj = travis(
        git_repo,
        sha,
        docker_user=docker_user,
        default_docker_image=default_docker_image,
        root_path=root_path,
    )
    return travis_obj.get_travis2docker()


if __name__ == '__main__':
    FNAME_SCRIPTS = main()
    stdout.write(
        'Script generated: \n' +
        '\n'.join(FNAME_SCRIPTS) +
        '\n'
    )
