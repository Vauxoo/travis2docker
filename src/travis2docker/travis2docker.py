import collections
import errno
import json
import os
import re
import shutil
import stat
from tempfile import gettempdir

import jinja2
import yaml

RE_ENV_STR = r"(?P<var>[\w]*)[ ]*[\=][ ]*[\"\']{0,1}" + \
             r"(?P<value>[\w\.\-\_/\$\{\}\:,\(\)\#\* ]*)[\"\']{0,1}"
RE_EXPORT_STR = r"^(?P<export>export|EXPORT)( )+" + RE_ENV_STR


class Travis2Docker(object):

    re_export = re.compile(RE_EXPORT_STR, re.M)

    @property
    def dockerfile_template(self):
        return self.jinja_env.get_template('Dockerfile')

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

    def __init__(self, yml_buffer, image=None, work_path=None, dockerfile=None,
                 templates_path=None, os_kwargs=None, copy_paths=None,
                 ):
        self.curr_work_path = None
        self.curr_exports = []
        self.build_extra_params = {}
        self.run_extra_params = {}
        if image is None:
            image = 'vauxoo/odoo-80-image-shippable-auto'
        if os_kwargs is None:
            os_kwargs = {}
        default_user = 'root'
        if image == 'vauxoo/odoo-80-image-shippable-auto':
            default_user = 'odoo'
        elif image == 'quay.io/travisci/travis-python':
            default_user = 'travis'
        os_kwargs.setdefault('user', default_user)
        if dockerfile is None:
            dockerfile = 'Dockerfile'
        if templates_path is None:
            templates_path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'templates')
        self.copy_paths = copy_paths
        self.os_kwargs = os_kwargs
        self.jinja_env = \
            jinja2.Environment(loader=jinja2.FileSystemLoader(templates_path))
        self.image = image
        self._sections = collections.OrderedDict()
        self._sections['env'] = 'env'
        self._sections['addons'] = 'addons'
        self._sections['before_install'] = 'run'
        self._sections['install'] = 'run'
        self._sections['script'] = 'entrypoint'
        self._sections['after_success'] = 'entrypoint'
        self.yml = yaml.load(yml_buffer)
        if work_path is None:
            base_name = os.path.splitext(os.path.basename(__file__))[0]
            self.work_path = os.path.join(gettempdir(), base_name)
        else:
            self.work_path = os.path.expandvars(os.path.expanduser(work_path))
        self.dockerfile = dockerfile

        travis_ci_apt_src = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            'travis-ci-apt-source-whitelist')
        self.ubuntu_json = json.load(
            open(os.path.join(travis_ci_apt_src, "ubuntu.json")))

    def _compute(self, section):
        section_type = self._sections.get(section)
        if not section_type:
            return None
        section_data = self.yml.get(section, "")
        if section != "env" and not section_data:
            return None
        if not isinstance(section_data, (list, dict, tuple)):
            section_data = [section_data]
        job_method = getattr(self, '_compute_' + section_type)
        return job_method(section_data, section)

    @staticmethod
    def _compute_env(data, _):
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
        for env_matrix in data.get('matrix', []):
            yield (env_globals + " " + env_matrix).strip()

    def _compute_run(self, data, section):
        args = self._make_script(data, section, add_run=True, prefix='files')
        return args

    def _compute_entrypoint(self, data, section):
        args = self._make_script(data, section, add_entrypoint=True,
                                 prefix='files')
        return args

    def _compute_addons(self, data, section):
        if 'apt' not in data:
            return
        sources = []
        for alias in (data['apt'].get('sources') or []):
            for ubuntu_source in self.ubuntu_json:
                if alias == ubuntu_source['alias']:
                    if ubuntu_source['key_url']:
                        sources.append(
                            'curl -sSL "' + ubuntu_source['key_url'] +
                            '" | apt-key add -')
                    if ubuntu_source['sourceline'].startswith('ppa:'):
                        sources.append(
                            'apt-add-repository -y "' +
                            ubuntu_source['sourceline'] + '"')
                    else:
                        sources.append(
                            'echo "' + ubuntu_source['sourceline'] +
                            '" | tee -a /etc/apt/sources.list > /dev/null')
        new_data = data['apt'].copy()
        new_data['sources'] = sources
        return new_data

    def _make_script(self, data, section, add_entrypoint=False, add_run=False,
                     prefix=""):
        file_path = os.path.join(self.curr_work_path, prefix, section)
        self.mkdir_p(os.path.dirname(file_path))
        with open(file_path, "w") as f_section:
            f_section.write('#!/bin/bash\n')
            for var, value in self.curr_exports:
                f_section.write('\nexport %s=%s' % (var, value))
            for line in data:
                self.curr_exports.extend([
                    (var, value)
                    for _, _, var, value in self.re_export.findall(line)])
                f_section.write('\n' + line)
            if section == 'script':
                f_section.write('\nsleep 2\n')
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

    def compute_build_scripts(self, prefix_build):
        build_path = os.path.join(self.curr_work_path, "10-build.sh")
        run_path = os.path.join(self.curr_work_path, "20-run.sh")
        new_image = self.new_image + '_' + str(prefix_build)
        with open(build_path, "w") as f_build, \
                open(run_path, "w") as f_run:
            build_content = self.build_template.render(
                image=new_image,
                dirname_dockerfile=self.curr_work_path,
                **self.build_extra_params
            ).strip('\n ')
            try:
                f_build.write(build_content.encode('utf-8'))
            except TypeError:
                f_build.write(build_content)

            run_content = self.run_template.render(
                image=new_image,
                **self.run_extra_params
            ).strip('\n ')
            try:
                f_run.write(run_content.encode('utf-8'))
            except TypeError:
                f_run.write(run_content)
        self.chmod_execution(build_path)
        self.chmod_execution(run_path)

    def _transform_yml_matrix2env(self):
        matrix = self.yml.pop('matrix', {})
        envs = [include['env'] for include in matrix.get('include', [])
                if include.get('env')]
        if envs:
            self.yml['env'] = envs

    def compute_dockerfile(self, skip_after_success=False):
        work_paths = []
        self._transform_yml_matrix2env()
        for count, env in enumerate(self._compute('env') or [], 1):
            self.reset()
            self.curr_work_path = os.path.join(self.work_path, str(count))
            curr_dockerfile = \
                os.path.join(self.curr_work_path, self.dockerfile)
            entryp_path = os.path.join(self.curr_work_path, "files",
                                       "entrypoint.sh")
            self.mkdir_p(os.path.dirname(entryp_path))
            entryp_relpath = os.path.relpath(entryp_path, self.curr_work_path)
            rvm_env_path = os.path.join(self.curr_work_path, "files",
                                        "rvm_env.sh")
            rvm_env_relpath = os.path.relpath(rvm_env_path, self.curr_work_path)
            copies = []
            for copy_path, dest in self.copy_paths:
                copies.append((self.copy_path(copy_path), dest))
            kwargs = {'runs': [], 'copies': copies, 'entrypoints': [],
                      'entrypoint_path': entryp_relpath, 'image': self.image,
                      'env': env, 'packages': [], 'sources': [],
                      'rvm_env_path': rvm_env_relpath,
                      }
            with open(curr_dockerfile, "w") as f_dockerfile, \
                    open(entryp_path, "w") as f_entrypoint, \
                    open(rvm_env_path, "w") as f_rvm:
                for section, _ in self._sections.items():
                    if section == 'env':
                        continue
                    if skip_after_success and section == 'after_success':
                        continue
                    result = self._compute(section)
                    if not result:
                        continue
                    keys_to_extend = ['copies', 'runs', 'entrypoints',
                                      'packages', 'sources'] \
                        if isinstance(result, dict) else []
                    for key_to_extend in keys_to_extend:
                        if key_to_extend in result:
                            kwargs[key_to_extend].extend(result[key_to_extend])
                kwargs.update(self.os_kwargs)
                dockerfile_content = \
                    self.dockerfile_template.render(kwargs).strip('\n ')
                try:
                    f_dockerfile.write(dockerfile_content.encode('utf-8'))
                except TypeError:
                    f_dockerfile.write(dockerfile_content)
                entrypoint_content = \
                    self.entrypoint_template.render(kwargs).strip('\n ')
                try:
                    f_entrypoint.write(entrypoint_content.encode('utf-8'))
                except TypeError:
                    f_entrypoint.write(entrypoint_content)
                rvm_env_content = self.jinja_env.get_template(
                    'rvm_env.sh').render(kwargs).strip('\n ')
                try:
                    f_rvm.write(rvm_env_content.encode('UTF-8'))
                except TypeError:
                    f_rvm.write(rvm_env_content)
            self.compute_build_scripts(count)
            self.chmod_execution(entryp_path)
            work_paths.append(self.curr_work_path)
        self.reset()
        return work_paths

    def copy_path(self, path):
        """
        :param paths list: List of paths to copy
        """
        src = os.path.expandvars(os.path.expanduser(path))
        basename = os.path.basename(src)
        dest_path = os.path.expandvars(os.path.expanduser(
            os.path.join(self.curr_work_path, basename)))
        if os.path.isdir(dest_path):
            shutil.rmtree(dest_path)
        if os.path.isdir(src):
            shutil.copytree(src, dest_path)
        elif os.path.isfile(src):
            shutil.copy(src, dest_path)
        else:
            raise UserWarning(
                "Just directory or file is supported to copy [%s]" % src)
        return os.path.relpath(dest_path, self.curr_work_path)
