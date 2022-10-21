# pylint: disable=useless-object-inheritance,consider-using-with,too-complex
import collections
import errno
import json
import os
import re
import shutil
import stat
from tempfile import gettempdir

import jinja2

try:
    from yaml import full_load as yaml_load
except ImportError:
    from yaml import load as yaml_load

RE_ENV_STR = r"(?P<var>[\w]*)[ ]*[\=][ ]*[\"\']{0,1}" + r"(?P<value>[\w\.\-\_/\$\{\}\:,\(\)\#\* ]*)[\"\']{0,1}"
RE_EXPORT_STR = r"^(?P<export>export|EXPORT)( )+" + RE_ENV_STR


class Travis2Docker(object):

    re_export = re.compile(RE_EXPORT_STR, re.M)

    @property
    def dockerfile_template(self):
        dockerfile = 'Dockerfile'
        if self.deployv:
            dockerfile += '_deployv'
        return self.jinja_env.get_template(dockerfile)

    @property
    def new_image(self):
        image_name = "%(repo_owner)s-%(repo_project)s" % self.os_kwargs
        revision = self.os_kwargs['revision']
        for invalid_char in '@:/#.':
            image_name = image_name.replace(invalid_char, '_')
            revision = revision.replace(invalid_char, '_')
        return ("%s:%s" % (image_name, revision)).lower()

    @property
    def entrypoint_template(self):
        return self.jinja_env.get_template('entrypoint.sh')

    @property
    def build_template(self):
        return self.jinja_env.get_template('10-build.sh')

    @property
    def run_template(self):
        return self.jinja_env.get_template('20-run.sh')

    @staticmethod
    def chmod_execution(file_path):
        os.chmod(file_path, os.stat(file_path).st_mode | stat.S_IEXEC)

    @staticmethod
    def mkdir_p(path):
        try:
            os.makedirs(path)
        except OSError as os_error:
            if os_error.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    def __init__(
        self,
        yml_buffer,
        image=None,
        work_path=None,
        dockerfile=None,
        templates_path=None,
        os_kwargs=None,
        copy_paths=None,
        runs_at_the_end_script=None,
        build_env_args=None,
        deployv=None,
    ):
        self._python_versions = []
        self.curr_work_path = None
        self.curr_exports = []
        self.build_extra_params = {}
        self.run_extra_params = {}
        self.build_env_args = build_env_args
        self.deployv = deployv
        self.runs_at_the_end_script = ["sleep 2"] if runs_at_the_end_script is None else runs_at_the_end_script
        self.variables_sh_data = {}
        if deployv:
            self.variables_sh_data = {
                var.lower(): value for _, _, var, value in self.re_export.findall(os_kwargs['variables_sh'])
            }
            self.variables_sh_data.update({"sha_short": os_kwargs["sha"][:7]})
            image = (
                "%(docker_image_repo)s:%(main_app)s-%(version)s-%(sha_short)s" % self.variables_sh_data
                if not image
                else image
            )
            build_sh = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', 'build.sh')
            entrypoint_sh = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'templates', 'entrypoint_deployv.sh'
            )
            docker_helper = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'docker_helper')
            vscode_conf = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', '.vscode')
            coveragerc = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates', '.coveragerc')
            copy_paths.append([build_sh, '/home/odoo/build.sh'])
            copy_paths.append([entrypoint_sh, '/entrypoint.sh'])
            copy_paths.append([docker_helper, '/home/odoo/build'])
            copy_paths.append([vscode_conf, '/home/odoo/.vscode'])
            copy_paths.append([coveragerc, '/home/odoo/.coveragerc'])
        if image is None:
            image = 'vauxoo/odoo-80-image-shippable-auto'
        if os_kwargs is None:
            os_kwargs = {}
        default_user = 'root'
        if image == 'vauxoo/odoo-80-image-shippable-auto' or deployv:
            default_user = 'odoo'
        elif image == 'quay.io/travisci/travis-python':
            default_user = 'travis'
        os_kwargs.setdefault('user', default_user)
        if dockerfile is None:
            dockerfile = 'Dockerfile'
        if templates_path is None:
            templates_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'templates')
        self.copy_paths = copy_paths
        self.os_kwargs = os_kwargs
        self.jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_path))
        self.image = image
        self._sections = collections.OrderedDict()
        self._sections['env'] = 'env'
        self._sections['addons'] = 'addons'
        self._sections['before_install'] = 'run'
        self._sections['install'] = 'run'
        self._sections['script'] = 'entrypoint'
        self._sections['after_success'] = 'entrypoint'
        self.yml = yaml_load(yml_buffer)
        if work_path is None:
            base_name = os.path.splitext(os.path.basename(__file__))[0]
            self.work_path = os.path.join(gettempdir(), base_name)
        else:
            self.work_path = os.path.expandvars(os.path.expanduser(work_path))
        self.dockerfile = dockerfile

        travis_ci_apt_src = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'travis-ci-apt-source-whitelist')
        self.ubuntu_json = json.load(
            open(os.path.join(travis_ci_apt_src, "ubuntu.json"))
        )  # pylint: disable=consider-using-with

    def _compute(self, section, yml=None):
        if yml is None:
            yml = self.yml
        section_type = self._sections.get(section)
        if not section_type:
            return None
        section_data = yml.get(section, "")
        if section != "env" and not section_data:
            return None
        if not isinstance(section_data, (list, dict, tuple)):
            section_data = [section_data]
        job_method = getattr(self, '_compute_' + section_type)
        return job_method(section_data, section, yml)

    def _compute_env(self, data, _, yml):
        if isinstance(data, list):
            # old version without matrix
            data = {'matrix': data}
        env_globals = ""
        for env_global in data.get('global', []):
            if isinstance(env_global, dict):
                # we can't use the secure encrypted variables
                continue
            env_globals += " " + env_global
        env_globals = env_globals.strip()
        psql_version = (yml.get('addons') or {}).get('postgresql')
        if psql_version:
            env_globals += ' PSQL_VERSION="%s"' % psql_version

        for env_matrix in data.get('matrix', ['']):
            yield (env_globals + " " + env_matrix).strip()

    def _compute_run(self, data, section, _):
        args = self._make_script(data, section, add_run=True, prefix='files')
        return args

    def _compute_entrypoint(self, data, section, _):
        args = self._make_script(data, section, add_entrypoint=True, prefix='files')
        return args

    def _compute_addons(self, data, section, _):
        if 'apt' not in data:
            return
        sources = []
        for alias in data['apt'].get('sources') or []:
            for ubuntu_source in self.ubuntu_json:
                if alias == ubuntu_source['alias']:
                    if ubuntu_source['key_url']:
                        sources.append('curl -sSL "' + ubuntu_source['key_url'] + '" | apt-key add -')
                    if ubuntu_source['sourceline'].startswith('ppa:'):
                        sources.append('apt-add-repository -y "' + ubuntu_source['sourceline'] + '"')
                    else:
                        sources.append(
                            'echo "' + ubuntu_source['sourceline'] + '" | tee -a /etc/apt/sources.list > /dev/null'
                        )
        new_data = data['apt'].copy()
        new_data['sources'] = sources
        return new_data

    def _make_script(self, data, section, add_entrypoint=False, add_run=False, prefix=""):
        file_path = os.path.join(self.curr_work_path, prefix, section)
        self.mkdir_p(os.path.dirname(file_path))
        with open(file_path, "w") as f_section:
            f_section.write('#!/bin/bash\n')
            for var, value in self.curr_exports:
                f_section.write('\nexport %s=%s' % (var, value))
            for line in data:
                self.curr_exports.extend([(var, value) for _, _, var, value in self.re_export.findall(line)])
                f_section.write('\n' + line)
            if section == 'script':
                for run_at_the_end_script in self.runs_at_the_end_script:
                    f_section.write('\n%s' % run_at_the_end_script)
        src = "./" + os.path.relpath(file_path, self.curr_work_path)
        dest = "/" + section
        args = {
            'copies': [(src, dest)],
            'entrypoints': [dest] if add_entrypoint else [],
            'runs': [dest] if add_run else [],
        }
        self.chmod_execution(file_path)
        return args

    def reset(self):
        self.curr_work_path = None
        self.curr_exports = []

    def compute_build_scripts(self, prefix_build, version):
        build_path = os.path.join(self.curr_work_path, "10-build.sh")
        run_path = os.path.join(self.curr_work_path, "20-run.sh")
        new_image = self.new_image + '_' + version.replace('.', '_') + '_' + str(prefix_build)
        with open(build_path, "w") as f_build, open(run_path, "w") as f_run:
            build_content = self.build_template.render(
                image=new_image, dirname_dockerfile=self.curr_work_path, **self.build_extra_params
            ).strip('\n ')
            try:
                f_build.write(build_content.encode('utf-8'))
            except TypeError:
                f_build.write(build_content)

            run_content = self.run_template.render(image=new_image, **self.run_extra_params).strip('\n ')
            try:
                f_run.write(run_content.encode('utf-8'))
            except TypeError:
                f_run.write(run_content)
        self.chmod_execution(build_path)
        self.chmod_execution(run_path)

    def _python_version_env(self):
        versions = self.yml.pop('python', {})
        if not versions:
            self._python_versions = ['3.5']  # 3.5 by default
            return
        if not isinstance(versions, list):
            versions = [versions]
        # TODO: Use full version if in the default base image are installed
        new_versions = {'.'.join(version.split('.')[:2]) for version in versions}
        self._python_versions = list(set(self._python_versions) | new_versions)

    def _transform_yml_matrix2env(self):
        matrix = self.yml.pop('matrix', {})
        envs = [include['env'] for include in matrix.get('include', []) if include.get('env')]
        if envs:
            self.yml['env'] = envs

    def compute_dockerfile(self, skip_after_success=False):
        work_paths = []
        self._transform_yml_matrix2env()
        self._python_version_env()
        jobs_stages = self.yml.pop('jobs', {}).get('include', {})
        for global_version in self._python_versions:
            for count, global_env in enumerate(self._compute('env'), 1):
                for job_count, job_stage in enumerate(jobs_stages or [{}], 1):
                    job_env = self._compute('env', job_stage) or ""
                    if job_env is not None:
                        job_env = next(job_env)
                    env = '%s %s' % (global_env, job_env)
                    env = env.strip()
                    version = global_version
                    try:
                        version = job_stage['python']
                    except KeyError:  # pylint: disable=except-pass
                        pass
                    version = "%s" % version

                    self.reset()
                    self.curr_work_path = os.path.join(
                        self.work_path, version.replace('.', '_'), "env_%d_job_%d" % (count, job_count)
                    )
                    curr_dockerfile = os.path.join(self.curr_work_path, self.dockerfile)
                    entryp_path = os.path.join(self.curr_work_path, "files", "entrypoint.sh")
                    self.mkdir_p(os.path.dirname(entryp_path))
                    entryp_relpath = os.path.relpath(entryp_path, self.curr_work_path)
                    rvm_env_path = os.path.join(self.curr_work_path, "files", "rvm_env.sh")
                    rvm_env_relpath = os.path.relpath(rvm_env_path, self.curr_work_path)
                    copies = []
                    for copy_path, dest in self.copy_paths:
                        copies.append((self.copy_path(copy_path), dest))
                    kwargs = {
                        'runs': [],
                        'copies': copies,
                        'entrypoints': [],
                        'entrypoint_path': entryp_relpath,
                        'python_version': version,
                        'image': self.image,
                        'env': env,
                        'packages': [],
                        'sources': [],
                        'rvm_env_path': rvm_env_relpath,
                        'build_env_args': self.build_env_args,
                    }
                    with open(curr_dockerfile, "w") as f_dockerfile, open(entryp_path, "w") as f_entrypoint, open(
                        rvm_env_path, "w"
                    ) as f_rvm:
                        for section, _ in self._sections.items():
                            if section == 'env':
                                continue
                            if skip_after_success and section == 'after_success':
                                continue
                            # job section replace global one
                            result = self._compute(section, job_stage)
                            if not result:
                                result = self._compute(section)
                            if not result:
                                continue
                            keys_to_extend = (
                                ['copies', 'runs', 'entrypoints', 'packages', 'sources']
                                if isinstance(result, dict)
                                else []
                            )
                            for key_to_extend in keys_to_extend:
                                if key_to_extend in result:
                                    kwargs[key_to_extend].extend(result[key_to_extend])
                        kwargs.update(self.os_kwargs)
                        dockerfile_content = self.dockerfile_template.render(kwargs).strip('\n ')
                        try:
                            f_dockerfile.write(dockerfile_content.encode('utf-8'))
                        except TypeError:
                            f_dockerfile.write(dockerfile_content)
                        entrypoint_content = self.entrypoint_template.render(kwargs).strip('\n ')
                        try:
                            f_entrypoint.write(entrypoint_content.encode('utf-8'))
                        except TypeError:
                            f_entrypoint.write(entrypoint_content)
                        rvm_env_content = self.jinja_env.get_template('rvm_env.sh').render(kwargs).strip('\n ')
                        try:
                            f_rvm.write(rvm_env_content.encode('UTF-8'))
                        except TypeError:
                            f_rvm.write(rvm_env_content)
                    self.compute_build_scripts(count, version)
                    self.chmod_execution(entryp_path)
                    work_paths.append(self.curr_work_path)
        self.reset()
        return work_paths

    def copy_path(self, path):
        """:param paths list: List of paths to copy"""
        src = os.path.expandvars(os.path.expanduser(path))
        basename = os.path.basename(src)
        dest_path = os.path.expandvars(os.path.expanduser(os.path.join(self.curr_work_path, basename)))
        if os.path.isdir(dest_path):
            shutil.rmtree(dest_path)
        if os.path.isdir(src):
            try:
                shutil.copytree(src, dest_path)
            except shutil.Error:  # pylint: disable=except-pass
                pass  # There are permissions errors to copy
        elif os.path.isfile(src):
            shutil.copy(src, dest_path)
        else:
            raise UserWarning("Just directory or file is supported to copy [%s]" % src)
        return os.path.relpath(dest_path, self.curr_work_path)
