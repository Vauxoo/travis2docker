#!/usr/bin/env python

import pathlib
import re
from glob import glob

from setuptools import find_packages, setup


def read(*names, **kwargs):
    return pathlib.Path(__file__).parent.joinpath(*names).read_text(encoding=kwargs.get("encoding", "utf8"))


setup(
    name="travis2docker",
    version="7.0.2",
    license="BSD-3-Clause",
    description="Script to generate a development Dockerfile from the deployv image of a repository",
    long_description="%s\n%s"
    % (
        re.compile(r"^.. start-badges.*^.. end-badges", re.MULTILINE | re.DOTALL).sub("", read("README.rst")),
        re.sub(r":[a-z]+:`~?(.*?)`", r"``\1``", read("CHANGELOG.rst")),
    ),
    long_description_content_type="text/x-rst",
    author="Vauxoo",
    author_email="info@vauxoo.com",
    url="https://github.com/vauxoo/travis2docker",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[pathlib.Path(path).stem for path in glob("src/*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Programming Language :: Python :: 3.15",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        # uncomment if you test on these interpreters:
        # 'Programming Language :: Python :: Implementation :: IronPython',
        # 'Programming Language :: Python :: Implementation :: Jython',
        # 'Programming Language :: Python :: Implementation :: Stackless',
        "Topic :: Utilities",
    ],
    keywords=[
        # eg: 'keyword1', 'keyword2', 'keyword3',
    ],
    python_requires=">=3.10",
    install_requires=read("requirements.txt").split("\n"),
    extras_require={
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
    },
    entry_points={
        "console_scripts": [
            "travisfile2dockerfile = travis2docker.cli:main",
        ]
    },
)
