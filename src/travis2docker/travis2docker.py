import collections
import errno
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
    curr_work_path = None
    curr_exports = []
    build_extra_params = {}
    run_extra_params = {}

    @property
    def dockerfile_template(self):
        return self.jinja_env.get_template('Dockerfile')

    @property
    def new_image(self):
        image_name = self.os_kwargs['repo_owner'] + '-' + \
            self.os_kwargs['repo_project'] + ':' + \
            self.os_kwargs['revision'].replace('/', '_')
        return image_name.lower()

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

    def __init__(self, yml_buffer, image, work_path=None, dockerfile=None,
                 templates_path=None, os_kwargs=None, copy_paths=None,
                 ):
        if os_kwargs is None:
            os_kwargs = {}
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

    def _compute(self, section):
        section_type = self._sections.get(section)
        if not section_type:
            return None
        section_data = self.yml.get(section, "")
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

    def _make_script(self, data, section, add_entrypoint=False, add_run=False,
                     prefix=""):
        file_path = os.path.join(self.curr_work_path, prefix, section)
        self.mkdir_p(os.path.dirname(file_path))
        with open(file_path, "w") as f_section:
            for var, value in self.curr_exports:
                f_section.write('\nexport %s=%s' % (var, value))
            for line in data:
                self.curr_exports.extend([
                    (var, value)
                    for _, _, var, value in self.re_export.findall(line)])
                f_section.write('\n' + line)
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
            self.curr_work_path = os.path.join(self.work_path, str(count))
            curr_dockerfile = \
                os.path.join(self.curr_work_path, self.dockerfile)
            entryp_path = os.path.join(self.curr_work_path, "files",
                                       "entrypoint.sh")
            self.mkdir_p(os.path.dirname(entryp_path))
            entryp_relpath = os.path.relpath(entryp_path, self.curr_work_path)
            copies = []
            for copy_path, dest in self.copy_paths:
                copies.append((self.copy_path(copy_path), dest))
            kwargs = {'runs': [], 'copies': copies, 'entrypoints': [],
                      'entrypoint_path': entryp_relpath, 'image': self.image,
                      'env': env,
                      }
            with open(curr_dockerfile, "w") as f_dockerfile, \
                    open(entryp_path, "w") as f_entrypoint:
                for section, _ in self._sections.items():
                    if section == 'env':
                        continue
                    if skip_after_success and section == 'after_success':
                        continue
                    result = self._compute(section)
                    if not result:
                        continue
                    keys_to_extend = ['copies', 'runs', 'entrypoints'] \
                        if isinstance(result, dict) else []
                    for key_to_extend in keys_to_extend:
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
        shutil.copytree(src, dest_path)
        return os.path.relpath(dest_path, self.curr_work_path)


# TODO: Migrate this code to tests
# if __name__ == '__main__':
#     yml_path_wrk = "/Users/moylop260/odoo/yoytec/.travis.yml"
#     yml_path_wrk = "~/odoo/l10n-argentina"
#     yml_path_wrk = "~/odoo/yoytec"
#     image_wrk = 'vauxoo/odoo-80-image-shippable-auto'
#     t2d = Travis2Docker(
#         yml_path_wrk, image_wrk, os_kwargs={
#             'user': 'shippable',
#             'repo_owner': 'Vauxoo',
#             'repo_project': 'yoytec',
#             'add_self_rsa_pub': True,
#             'remotes': ['Vauxoo', 'Vauxoo-dev'],
#             'revision': 'pull/2',
#             'git_email': 'moylop@vx.com',
#             'git_user': 'moy6',
#         },
#         copy_paths=[("$HOME/.ssh", "$HOME/.ssh")]
#     )
#     t2d.run_extra_params = "-itd --entrypoint=bash -e TRAVIS_PULL_REQUEST=1"
#     t2d.build_extra_params = "--rm"
#     t2d.compute_dockerfile(skip_after_success=True)
#     print t2d.work_path
