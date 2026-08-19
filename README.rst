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

Script to generate a development Dockerfile from the deployv image of a repository (based on its ``variables.sh`` file)

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
For private repositories use the ssh url.

For more information execute:
 `travisfile2dockerfile --help`

Example:
 `travisfile2dockerfile --root-path=$HOME/t2d git@github.com:Vauxoo/forecast.git 8.0`

The output is:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0`

To build image:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/10-build.sh`

To create container:
 `${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/20-run.sh --entrypoint=bash`

The repository needs a ``variables.sh`` file in its root path (the one used by
the deployv images built from the CI). By default the docker image is built
from its values as ``DOCKER_IMAGE_REPO:MAIN_APP-VERSION-SHA_SHORT``; use
``--docker-image=quay.io/vauxoo/PROJECT:TAG`` to pick the image pushed by the
``build_docker`` pipeline instead.

Optional build steps (``--build-env-args``)
===========================================

Some development tools and build steps are **not** enabled by default. They are
enabled with a flag passed as a build environment variable using
``--build-env-args``, which generates an ``ENV <FLAG>=TRUE`` line in the
Dockerfile. If the flag is not defined, the step is skipped.

.. list-table::
    :widths: 30 70
    :header-rows: 1

    * - Flag
      - Enables
    * - ``VIM_INSTALL``
      - vim + spf13-vim, vim-openerp, jedi-vim, wakatime and the pylint_odoo/eslint syntastic configuration
    * - ``ZSH_INSTALL``
      - zsh + oh-my-zsh with the ``odoo-shippable`` theme
    * - ``CHOWN_UID_GID``
      - Aligns the odoo user UID/GID to 5410 to match OrchestSH images. Slow: it re-chowns the whole filesystem

Example enabling more than one::

    travisfile2dockerfile --build-env-args VIM_INSTALL ZSH_INSTALL \
        git@github.com:Vauxoo/forecast.git 8.0

VS Code support (``DEPLOYV_VSCODE``)
====================================

Opt-in with the environment variable ``DEPLOYV_VSCODE=1``::

    DEPLOYV_VSCODE=1 travisfile2dockerfile git@github.com:Vauxoo/forecast.git 8.0

It is disabled by default so vim/terminal users do not pay the extra build
time. When enabled:

- The Dockerfile pre-installs the VS Code server and the extensions listed in
  ``templates/.vscode/extensions.json`` at **build** time, so attaching VS Code
  to the container does not download anything live. The server version is
  pinned to the commit of your local ``code`` binary when available (run
  ``travisfile2dockerfile`` again after upgrading VS Code to re-pin it);
  otherwise the latest stable server is used. If the pinned server does not
  match your client, VS Code just falls back to downloading its own version;
  the pre-installed extensions are version-independent and are reused anyway.
- A ``.devcontainer.json`` is generated next to the Dockerfile pointing to the
  image built by ``10-build.sh``, so opening that folder in VS Code offers
  "Reopen in Container" automatically.

codebase-memory-deployv
=======================

The image ships with `codebase-memory-deployv
<https://pypi.org/project/codebase-memory-deployv>`__, a wrapper that deploys
`codebase-memory-mcp <https://github.com/DeusData/codebase-memory-mcp>`__
(code knowledge graph for AI agents) for instances following this layout.

The repository is **not** indexed while building the image. Run inside the
container::

    codebase-memory-deployv

It installs codebase-memory-mcp if it is missing, derives the project name from
``${MAIN_REPO_FULL_PATH}/variables.sh`` (e.g. ``forecast_17.0``), and indexes
``/home/odoo/instance`` in batches of modules. Indexing takes a few minutes on
a big instance, so it is left as an explicit step for the user.

Depends
=======

SSH key without password
************************

Dockerfile doesn't support a prompt to enter your password, so you need to remove it from your ssh keys.

Recommended: use Ed25519 keys. The tool copies ``~/.ssh/id_ed25519.pub`` to the
container's ``authorized_keys`` and warns if only RSA keys are found.

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
