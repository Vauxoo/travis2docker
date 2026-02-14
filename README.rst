========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |github-actions|
        | |codecov|
    * - package
      - |version| |downloads| |wheel| |supported-versions| |supported-implementations|

.. |docs| image:: https://readthedocs.org/projects/travis2docker/badge/?style=flat
    :target: https://readthedocs.org/projects/travis2docker
    :alt: Documentation Status

.. |github-actions| image:: https://github.com/Vauxoo/travis2docker/actions/workflows/github-actions.yml/badge.svg
    :alt: GitHub Actions Build Status
    :target: https://github.com/Vauxoo/travis2docker/actions

.. |codecov| image:: https://codecov.io/gh/Vauxoo/travis2docker/branch/main/graph/badge.svg
    :alt: Coverage Status
    :target: https://codecov.io/gh/Vauxoo/travis2docker

.. |version| image:: https://img.shields.io/pypi/v/travis2docker.svg?style=flat
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/travis2docker

.. |downloads| image:: https://img.shields.io/pypi/dm/travis2docker.svg?style=flat
    :alt: PyPI Package monthly downloads
    :target: https://pypi.python.org/pypi/travis2docker

.. |wheel| image:: https://img.shields.io/pypi/wheel/travis2docker.svg?style=flat
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/travis2docker

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/travis2docker.svg?style=flat
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/travis2docker

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/travis2docker.svg?style=flat
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/travis2docker

.. .. |commits-since| image:: https://img.shields.io/github/commits-since/Vauxoo/travis2docker/v3.5.0.svg
..     :alt: Commits since latest release
..     :target: https://github.com/Vauxoo/travis2docker/compare/v3.5.0...main

.. end-badges

Script to generate Dockerfile from .travis.yml file

* Free software: BSD license

Installation
============

::

    pip install travis2docker

Usage
=====

`travisfile2dockerfile REPO_URL BRANCH`

Or with pull request
 `travisfile2dockerfile REPO_URL pull/##`

In REPO_URL use the ssh or https url of the git repository.

The tool reads the ``.travis.yml`` (or ``.t2d.yml``) file from the repository and
branch specified, generating Dockerfiles and helper scripts.

For more information execute:
 `travisfile2dockerfile --help`

Example:
 `travisfile2dockerfile --root-path=$HOME/t2d git@github.com:Vauxoo/forecast.git 8.0`

The output is:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/2_7/env_1_job_1`
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/2_7/env_2_job_1`

Where ``2_7`` is the Python version (dots replaced by underscores), and
``env_N_job_M`` identifies the environment/job matrix combination.

To build image:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/2_7/env_1_job_1/10-build.sh`

To create container:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/2_7/env_1_job_1/20-run.sh --entrypoint=bash`

To run the test (inside of container):
 `/entrypoint.sh`

Depends
=======

SSH key without password
************************

Dockerfile doesn't support a prompt to enter your password, so you need to remove it from your ssh keys.

Recommended: use Ed25519 keys (the tool will warn if only RSA is found).

::

  export fname=~/.ssh/id_ed25519
  cp ${fname} ${fname}_with_pwd
  ssh-keygen -p -N "" -f ${fname}

For legacy RSA keys:

::

  export fname=~/.ssh/id_rsa
  cp ${fname} ${fname}_with_pwd
  openssl rsa -in ${fname} -out ${fname}_without_pwd
  cp ${fname}_without_pwd ${fname}

Download the big image
**********************

Travis2docker uses a default image with many packages pre-installed.
The ``10-build.sh`` script uses ``docker build --pull`` which will fetch the
image automatically, but you can pre-download it:

`docker pull vauxoo/odoo-80-image-shippable-auto`

Note: You can define a custom image to use with `--docker-image` parameter.

For example if you want use the original image of travis you can add the following parameters:

`--docker-image=quay.io/travisci/travis-python --docker-user=travis`

Install docker
**************

https://docs.docker.com/engine/installation/

Documentation
=============

https://travis2docker.readthedocs.io/

Development
===========

To run the all tests run::

    tox

Note, to combine the coverage data from all the tox environments run:

.. list-table::
    :widths: 10 90
    :stub-columns: 1

    - - Windows
      - ::

            set PYTEST_ADDOPTS=--cov-append
            tox

    - - Other
      - ::

            PYTEST_ADDOPTS=--cov-append tox
