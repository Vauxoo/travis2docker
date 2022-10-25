# No logger planned to use here
# pylint: disable=print-used,consider-using-with
from __future__ import print_function

import os
import subprocess
import sys

from travis2docker.cli import main as cli_main

try:
    from shutil import which  # python3.x
except ImportError:
    from whichcraft import which


def main():
    return cli_main(return_result=True)


def check_failed_dockerfile(scripts, lines_required=None):
    npm_bin = which('npm')
    npm_bin_path = subprocess.check_output([npm_bin, 'bin']).decode('UTF-8').strip('\n') if npm_bin else ""
    npm_bin_path_g = subprocess.check_output([npm_bin, 'bin', '-g']).decode('UTF-8').strip('\n') if npm_bin else ""
    lint_bin_name = 'dockerfile_lint'
    lint_bin = which(lint_bin_name) or which(lint_bin_name, path=npm_bin_path + os.pathsep + npm_bin_path_g)
    assert lint_bin, "'%s' not found." % lint_bin_name
    for script in scripts:
        fname_dkr = os.path.join(script, 'Dockerfile')
        pipe = subprocess.Popen([lint_bin, "-f", fname_dkr], stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
        output = pipe.stdout.read().decode('utf-8')
        assert 'Check passed' in output, fname_dkr
        print("Check dockerfile output", output)
        if not lines_required:
            continue
        with open(fname_dkr) as fdkr:
            fdkr_lines = fdkr.readlines()
            fdkr_lines[-1] = fdkr_lines[-1].strip('\n') + '\n'
            for line_required in lines_required:
                assert line_required + '\n' in fdkr_lines
            print(fdkr_lines)


def test_main():
    # TODO: fix duplicated code
    dirname_example = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'examples')
    argv = ['travis2docker', 'foo', 'bar', '--no-clone']
    sources_py = "source ${REPO_REQUIREMENTS}/virtualenv/" + "python2.7/bin/activate"
    sources_js = "source ${REPO_REQUIREMENTS}/virtualenv/nodejs/bin/activate"
    lines_required = [
        'RUN /bin/bash -c "{source_py} && {source_js} '
        '&& source /rvm_env.sh && /install"'.format(source_py=sources_py, source_js=sources_js),
        'ENTRYPOINT /entrypoint.sh',
    ]

    example = os.path.join(dirname_example, 'example_1.yml')
    sys.argv = argv + ['--travis-yml-path', example, '--add-rcfile=%s,%s' % (example, dirname_example)]
    scripts = main()
    assert len(scripts) == 1, 'Scripts returned should be 1 for %s' % example
    check_failed_dockerfile(scripts, lines_required)
    assert os.path.isdir(os.path.join(scripts[0], os.path.basename(dirname_example)))
    assert os.path.isfile(os.path.join(scripts[0], os.path.basename(example)))

    sys.argv = argv + ['--travis-yml-path', example, '--docker-image', 'quay.io/travisci/travis-python']
    scripts = main()
    assert len(scripts) == 1, 'Scripts returned should be 1 for %s' % example
    check_failed_dockerfile(scripts, ['FROM quay.io/travisci/travis-python'])

    example = os.path.join(dirname_example, 'example_2.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 1, 'Scripts returned should be 1 for %s' % example
    check_failed_dockerfile(scripts, lines_required + ['ENV VARIABLE="value"'])

    example = os.path.join(dirname_example, 'example_3.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 2, 'Scripts returned should be 2 for %s' % example
    check_failed_dockerfile(scripts, lines_required)
    with open(os.path.join(scripts[0], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'VARIABLE_MATRIX_1="value matrix 1"' in dkr_content
        assert 'ENV VARIABLE_GLOBAL="value global"' in dkr_content
        assert 'RUN apt-add-repository' in dkr_content
    with open(os.path.join(scripts[1], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'VARIABLE_MATRIX_2="value matrix 2"' in dkr_content
        assert 'ENV VARIABLE_GLOBAL="value global"' in dkr_content
        assert 'RUN apt-add-repository' in dkr_content

    example = os.path.join(dirname_example, 'example_4.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 2, 'Scripts returned should be 2 for %s' % example
    check_failed_dockerfile(scripts)
    with open(os.path.join(scripts[0], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'VARIABLE_INCLUDE_1="value include 1"' in dkr_content
    with open(os.path.join(scripts[1], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'VARIABLE_INCLUDE_2="value include 2"' in dkr_content

    # Tests that, when specified, the postgresql key sets
    # automatically the environment variable $PSQL_VERSION
    example = os.path.join(dirname_example, 'example_5.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 2, 'Scripts returned should be 2 for %s' % example
    check_failed_dockerfile(scripts)
    with open(os.path.join(scripts[0], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert ' PSQL_VERSION="9.5" ' in dkr_content
    with open(os.path.join(scripts[1], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert ' PSQL_VERSION="9.5" ' in dkr_content

    url = 'https://github.com/Vauxoo/travis2docker.git'
    sys.argv = ['travis2docker', url, 'main']
    scripts = main()
    sources_py = "source ${REPO_REQUIREMENTS}/virtualenv/" + "python3.5/bin/activate"
    lines_required.pop(0)
    lines_required.append(
        'RUN /bin/bash -c "{source_py} && {source_js} && '
        'source /rvm_env.sh && '
        '/before_install && /install"'.format(source_py=sources_py, source_js=sources_js),
    )
    check_failed_dockerfile(scripts, lines_required + ['ENV TRAVIS_REPO_SLUG=Vauxoo/travis2docker'])

    sys.argv = ['travis2docker', url, 'pull/54']
    scripts = main()
    check_failed_dockerfile(scripts, lines_required + ['ENV TRAVIS_REPO_SLUG=Vauxoo/travis2docker'])

    sys.argv += ['--build-env-args', 'BUILD_ENV1', '--build-env-args', 'BUILD_ENV2']
    scripts = main()
    check_failed_dockerfile(
        scripts,
        lines_required
        + [
            'ARG BUILD_ENV1',
            'ENV BUILD_ENV1=$BUILD_ENV1',
            'ARG BUILD_ENV2',
            'ENV BUILD_ENV2=$BUILD_ENV2',
        ],
    )
