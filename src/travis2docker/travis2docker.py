# pylint: disable=useless-object-inheritance,consider-using-with,print-used
import os
import pathlib
import re
import shutil
import stat
from tempfile import gettempdir

import jinja2

RE_ENV_STR = r"(?P<var>[\w]*)[ ]*[\=][ ]*[\"\']{0,1}" + r"(?P<value>[\w\.\-\_/\$\{\}\:,\(\)\#\* ]*)[\"\']{0,1}"
RE_EXPORT_STR = r"^(?P<export>export|EXPORT)( )+" + RE_ENV_STR


class Travis2Docker:
    re_export = re.compile(RE_EXPORT_STR, re.MULTILINE)

    @property
    def dockerfile_template(self):
        return self.jinja_env.get_template("Dockerfile_deployv")

    @property
    def new_image(self):
        image_name = "%(repo_owner)s-%(repo_project)s" % self.os_kwargs
        revision = self.os_kwargs["revision"]
        for invalid_char in "@:/#.":
            image_name = image_name.replace(invalid_char, "_")
            revision = revision.replace(invalid_char, "_")
        return ("%s:%s" % (image_name, revision)).lower()

    @property
    def build_template(self):
        return self.jinja_env.get_template("10-build.sh")

    @property
    def run_template(self):
        return self.jinja_env.get_template("20-run.sh")

    @staticmethod
    def chmod_execution(file_path):
        pathlib.Path(file_path).chmod(os.stat(file_path).st_mode | stat.S_IEXEC)

    @staticmethod
    def mkdir_p(path):
        pathlib.Path(path).mkdir(exist_ok=True, parents=True)

    def __init__(
        self,
        image=None,
        work_path=None,
        dockerfile=None,
        templates_path=None,
        os_kwargs=None,
        copy_paths=None,
        build_env_args=None,
        build_extra_steps=None,
    ):
        self.curr_work_path = None
        self.build_extra_params = {}
        self.run_extra_params = {}
        self.build_env_args = build_env_args
        self.build_extra_steps = build_extra_steps
        if os_kwargs is None:
            os_kwargs = {}
        if copy_paths is None:
            copy_paths = []
        self.variables_sh_data = {
            var.lower(): value for _, _, var, value in self.re_export.findall(os_kwargs["variables_sh"])
        }
        self.variables_sh_data.update({"sha_short": os_kwargs["sha"][:7]})
        if not image:
            image = "%(docker_image_repo)s:%(main_app)s-%(version)s-%(sha_short)s" % self.variables_sh_data
        templates_dir = os.path.join(pathlib.Path(os.path.realpath(__file__)).parent, "templates")
        build_sh = os.path.join(templates_dir, "build.sh")
        entrypoint_sh = os.path.join(templates_dir, "entrypoint_deployv.sh")
        docker_helper = os.path.join(pathlib.Path(os.path.realpath(__file__)).parent, "docker_helper")
        vscode_conf = os.path.join(templates_dir, ".vscode")
        coveragerc = os.path.join(templates_dir, ".coveragerc")
        copy_paths.append([build_sh, "/home/odoo/build.sh"])
        copy_paths.append([entrypoint_sh, "/entrypoint.sh"])
        copy_paths.append([docker_helper, "/home/odoo/build"])
        copy_paths.append([vscode_conf, "/home/odoo/.vscode"])
        copy_paths.append([coveragerc, "/home/odoo/.coveragerc"])
        os_kwargs.setdefault("user", "odoo")
        if dockerfile is None:
            dockerfile = "Dockerfile"
        if templates_path is None:
            templates_path = templates_dir
        self.copy_paths = copy_paths
        self.os_kwargs = os_kwargs
        self.jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_path))
        self.image = image
        if work_path is None:
            base_name = os.path.splitext(pathlib.Path(__file__).name)[0]
            self.work_path = os.path.join(gettempdir(), base_name)
        else:
            self.work_path = os.path.expandvars(pathlib.Path(work_path).expanduser())
        self.dockerfile = dockerfile

    def compute_build_scripts(self):
        build_path = os.path.join(self.curr_work_path, "10-build.sh")
        run_path = os.path.join(self.curr_work_path, "20-run.sh")
        with pathlib.Path(build_path).open("w") as f_build, pathlib.Path(run_path).open("w") as f_run:
            build_content = self.build_template.render(
                image=self.new_image, dirname_dockerfile=self.curr_work_path, **self.build_extra_params
            ).strip("\n ")
            f_build.write(build_content)
            run_content = self.run_template.render(image=self.new_image, **self.run_extra_params).strip("\n ")
            f_run.write(run_content)
        self.chmod_execution(build_path)
        self.chmod_execution(run_path)

    def compute_dockerfile(self):
        self.curr_work_path = self.work_path
        curr_dockerfile = os.path.join(self.curr_work_path, self.dockerfile)
        self.mkdir_p(self.curr_work_path)
        copies = []
        for copy_path, dest in self.copy_paths:
            copies.append((self.copy_path(copy_path), dest))
        self.set_authorized_key()
        kwargs = {
            "copies": copies,
            "image": self.image,
            "build_env_args": self.build_env_args,
            "build_extra_steps": self.build_extra_steps,
        }
        kwargs.update(self.os_kwargs)
        with pathlib.Path(curr_dockerfile).open("w") as f_dockerfile:
            dockerfile_content = self.dockerfile_template.render(kwargs).strip("\n ")
            f_dockerfile.write(dockerfile_content)
        self.compute_build_scripts()
        work_paths = [self.curr_work_path]
        self.curr_work_path = None
        return work_paths

    def copy_path(self, path):
        """:param paths list: List of paths to copy"""
        src = os.path.expandvars(pathlib.Path(path).expanduser())
        basename = pathlib.Path(src).name
        dest_path = os.path.expandvars(pathlib.Path(os.path.join(self.curr_work_path, basename)).expanduser())
        if pathlib.Path(dest_path).is_dir():
            shutil.rmtree(dest_path)
        if pathlib.Path(src).is_dir():
            try:
                shutil.copytree(src, dest_path)
            except shutil.Error:  # pylint: disable=except-pass
                pass  # There are permissions errors to copy
        elif pathlib.Path(src).is_file():
            shutil.copy(src, dest_path)
        else:
            raise UserWarning("Just directory or file is supported to copy [%s]" % src)
        return os.path.relpath(dest_path, self.curr_work_path)

    def set_authorized_key(self):
        ssh_dir = pathlib.Path("~/.ssh").expanduser()
        ed_key = os.path.join(ssh_dir, "id_ed25519.pub")
        rsa_key = os.path.join(ssh_dir, "id_rsa.pub")

        to_copy = False
        if pathlib.Path(ed_key).is_file():
            to_copy = ed_key
        elif pathlib.Path(rsa_key).is_file():
            print("RSA keys are deprecated, consider changing to ed25519")
            to_copy = rsa_key

        if not to_copy:
            print("No public key found. No key added to ~/.ssh/authorized_keys. SSH login won't work.")
            return

        pub_key = pathlib.Path(to_copy).read_text(encoding="utf-8")

        with pathlib.Path(os.path.join(self.curr_work_path, ".ssh", "authorized_keys")).open(
            "a", encoding="utf-8"
        ) as auth_fd:
            auth_fd.write(pub_key)
