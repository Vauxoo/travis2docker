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
 
In REPO_URL use the ssh url of github.

For more information execute:
 `travisfile2dockerfile --help`
 
Example:
 `travisfile2dockerfile --root-path=$HOME/t2d git@github.com:Vauxoo/forecast.git 8.0`

The output is:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/1`
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/2`

The first one is the build for env `TESTS=1`, the second one is for env with `LINT_CHECK=1`

To build image:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/1/10-build.sh`

To create container:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/1/20-run.sh --entrypoint=bash`

To run the test (into of container):
 `/entrypoint.sh`

Depends
=======

SSH key without password
************************

Dockerfile doesn't support a prompt to enter your password, so you need to remove it from your ssh keys.

::

  export fname=~/.ssh/id_rsa
  cp ${fname} ${fname}_with_pwd
  openssl rsa -in ${fname} -out ${fname}_without_pwd
  cp ${fname}_without_pwd ${fname}

Download the big image
**********************

Travis2docker uses a default image with many packages pre-installed.

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


Release process
===============

This project uses `bump2version <https://github.com/c4urself/bump2version>`_ to
manage version bumps across ``.bumpversion.cfg``, ``docs/conf.py``,
``setup.py`` and ``src/travis2docker/__init__.py``.

Requirements
************

* Write access to push to ``main`` and to push tags.
* A GPG key configured for signing git tags. The CI pipeline that publishes
  the package to PyPI only builds from **signed** tags::

      git config --global user.signingkey <YOUR_GPG_KEY_ID>

* ``bump2version`` installed::

      pip install bump2version

Steps to release a new version
******************************


1. Make sure you are on ``main`` and it is up to date, with no local commits
   ahead of ``origin``::

       git checkout main
       git pull origin main
       git status  # must be clean

2. Bump the version. This creates a commit and a tag automatically
   (choose ``patch``, ``minor`` or ``major`` as needed)::

       bump2version patch

   This updates::

       .bumpversion.cfg
       docs/conf.py
       setup.py
       src/travis2docker/__init__.py

3. Verify the tag was created and that it is **signed**::

       git tag -v vX.Y.Z

   If ``sign_tags`` is not enabled in ``.bumpversion.cfg``, the tag created
   in step 2 will **not** be signed and the CI build/publish step will not
   run. In that case, re-create the tag manually before pushing::

       git tag -d vX.Y.Z
       git tag -s vX.Y.Z -m "vX.Y.Z"

   To avoid this every time, add the following to ``.bumpversion.cfg``::

       [bumpversion]
       current_version = X.Y.Z
       commit = True
       tag = True
       sign_tags = True

4. Push the branch and the tag::

       git push origin main --tags

   Pushing the signed tag is what triggers the CI job that builds and
   publishes the package to PyPI.

Troubleshooting
***************

* **"tag already exists" / dirty working tree**: make sure ``git status`` is
  clean and ``git pull origin main`` was run before ``bump2version``,
  otherwise the bump commit/tag will be based on stale history.
* **CI does not trigger a PyPI build**: check that the pushed tag is signed
  (``git tag -v vX.Y.Z`` should show a valid GPG signature) and that
  ``user.signingkey`` is configured correctly.
