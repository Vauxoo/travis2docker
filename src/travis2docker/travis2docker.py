# pylint: disable=useless-object-inheritance,consider-using-with
import json
import logging
import pathlib
import re
import shutil
import stat
import subprocess
from tempfile import gettempdir

import jinja2

_logger = logging.getLogger(__name__)

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
        file_path.chmod(file_path.stat().st_mode | stat.S_IEXEC)

    @staticmethod
    def get_vscode_version():
        """Return "commit:SHA" of the local VS Code client to pre-install the matching
        server into the image, or "latest" if there is no "code" binary available"""
        code_bin = shutil.which("code")
        if code_bin:
            try:
                lines = subprocess.check_output([code_bin, "--version"]).decode("UTF-8").splitlines()
                if len(lines) >= 2 and lines[1].strip():
                    return "commit:%s" % lines[1].strip()
            except (subprocess.CalledProcessError, OSError):
                pass
        return "latest"

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
        vscode=False,
    ):
        self.curr_work_path = None
        self.vscode = vscode
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
        module_dir = pathlib.Path(__file__).resolve().parent
        templates_dir = module_dir / "templates"
        copy_paths.append([templates_dir / "build.sh", "/home/odoo/build.sh"])
        copy_paths.append([templates_dir / "entrypoint_deployv.sh", "/entrypoint.sh"])
        copy_paths.append([module_dir / "docker_helper", "/home/odoo/build"])
        copy_paths.append([templates_dir / ".vscode", "/home/odoo/.vscode"])
        copy_paths.append([templates_dir / ".coveragerc", "/home/odoo/.coveragerc"])
        os_kwargs.setdefault("user", "odoo")
        if self.vscode:
            extensions_data = json.loads((templates_dir / ".vscode" / "extensions.json").read_text())
            os_kwargs.setdefault("vscode_extensions", extensions_data["recommendations"])
            os_kwargs.setdefault("vscode_version", self.get_vscode_version())
        if dockerfile is None:
            dockerfile = "Dockerfile"
        if templates_path is None:
            templates_path = templates_dir
        self.copy_paths = copy_paths
        self.os_kwargs = os_kwargs
        self.jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_path))
        self.image = image
        if work_path is None:
            self.work_path = pathlib.Path(gettempdir()) / pathlib.Path(__file__).stem
        else:
            self.work_path = pathlib.Path(work_path).expanduser()
        self.dockerfile = dockerfile

    def compute_build_scripts(self):
        build_path = self.curr_work_path / "10-build.sh"
        run_path = self.curr_work_path / "20-run.sh"
        with build_path.open("w") as f_build, run_path.open("w") as f_run:
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
        curr_dockerfile = self.curr_work_path / self.dockerfile
        self.curr_work_path.mkdir(exist_ok=True, parents=True)
        copies = []
        for copy_path, dest in self.copy_paths:
            copies.append((self.copy_path(copy_path), dest))
        self.set_authorized_key()
        kwargs = {
            "copies": copies,
            "image": self.image,
            "build_env_args": self.build_env_args,
            "build_extra_steps": self.build_extra_steps,
            "vscode": self.vscode,
        }
        kwargs.update(self.os_kwargs)
        with curr_dockerfile.open("w") as f_dockerfile:
            dockerfile_content = self.dockerfile_template.render(kwargs).strip("\n ")
            f_dockerfile.write(dockerfile_content)
        if self.vscode:
            self.compute_devcontainer()
        self.compute_build_scripts()
        work_paths = [str(self.curr_work_path)]
        self.curr_work_path = None
        return work_paths

    def compute_devcontainer(self):
        """Generate a .devcontainer.json so VS Code offers reopening the generated
        image as a Development Container"""
        name = self.os_kwargs.get("repo_project") or self.variables_sh_data.get("main_app", "odoo")
        devcontainer_content = self.jinja_env.get_template("devcontainer.json").render(
            image=self.new_image, name=name, **self.os_kwargs
        )
        (self.curr_work_path / ".devcontainer.json").write_text(devcontainer_content)

    def copy_path(self, path):
        """:param paths list: List of paths to copy"""
        src = pathlib.Path(path).expanduser()
        dest_path = self.curr_work_path / src.name
        if dest_path.is_dir():
            shutil.rmtree(dest_path)
        if src.is_dir():
            try:
                shutil.copytree(src, dest_path)
            except shutil.Error:  # ruff: ignore[except-pass]
                pass  # There are permissions errors to copy
        elif src.is_file():
            shutil.copy(src, dest_path)
        else:
            raise UserWarning("Just directory or file is supported to copy [%s]" % src)
        return str(dest_path.relative_to(self.curr_work_path))

    def set_authorized_key(self):
        ssh_dir = pathlib.Path("~/.ssh").expanduser()
        ed_key = ssh_dir / "id_ed25519.pub"
        rsa_key = ssh_dir / "id_rsa.pub"

        to_copy = None
        if ed_key.is_file():
            to_copy = ed_key
        elif rsa_key.is_file():
            _logger.warning("RSA keys are deprecated, consider changing to ed25519")
            to_copy = rsa_key

        if not to_copy:
            _logger.warning("No public key found. No key added to ~/.ssh/authorized_keys. SSH login won't work.")
            return

        pub_key = to_copy.read_text(encoding="utf-8")

        with (self.curr_work_path / ".ssh" / "authorized_keys").open("a", encoding="utf-8") as auth_fd:
            auth_fd.write(pub_key)
