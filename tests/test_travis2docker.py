
import os
import subprocess
import sys

from travis2docker.cli import main


def check_failed_dockerfile(scripts):
    for script in scripts:
        fname_dkr = os.path.join(script, 'Dockerfile')
        pipe = subprocess.Popen(["dockerfile_lint", "-f", fname_dkr],
                                stderr=subprocess.STDOUT,
                                stdout=subprocess.PIPE)
        output = pipe.stdout.read().decode('utf-8')
        assert 'Check passed' in output


def test_main():
    # TODO: fix duplicated code
    dirname_example = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), '..', 'examples')
    argv = ['travis2docker', 'foo', 'bar', '--no-clone']

    example = os.path.join(dirname_example, 'example_1.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 1, 'Scripts returned should be 1 for %s' % example
    check_failed_dockerfile(scripts)

    example = os.path.join(dirname_example, 'example_2.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 1, 'Scripts returned should be 1 for %s' % example
    check_failed_dockerfile(scripts)
    with open(os.path.join(scripts[0], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'ENV VARIABLE="value"' in dkr_content

    example = os.path.join(dirname_example, 'example_3.yml')
    sys.argv = argv + ['--travis-yml-path', example]
    scripts = main()
    assert len(scripts) == 2, 'Scripts returned should be 2 for %s' % example
    check_failed_dockerfile(scripts)
    with open(os.path.join(scripts[0], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'VARIABLE_GLOBAL="value global"' in dkr_content
        assert 'VARIABLE_MATRIX_1="value matrix 1"' in dkr_content
    with open(os.path.join(scripts[1], 'Dockerfile')) as f_dkr:
        dkr_content = f_dkr.read()
        assert 'VARIABLE_GLOBAL="value global"' in dkr_content
        assert 'VARIABLE_MATRIX_2="value matrix 2"' in dkr_content

    url = 'https://github.com/Vauxoo/travis2docker.git'
    sys.argv = ['travis2docker', url, 'master']
    scripts = main()
    check_failed_dockerfile(scripts)
    for script in scripts:
        fname_dkr = os.path.join(script, 'Dockerfile')
        with open(fname_dkr) as f_dkr:
            dkr_content = f_dkr.read()
            assert 'ENV TRAVIS_REPO_SLUG=Vauxoo/travis2docker' in dkr_content

    sys.argv = ['travis2docker', url, 'pull/54']
    scripts = main()
    check_failed_dockerfile(scripts)
    for script in scripts:
        fname_dkr = os.path.join(script, 'Dockerfile')
        with open(fname_dkr) as f_dkr:
            dkr_content = f_dkr.read()
            assert 'ENV TRAVIS_REPO_SLUG=Vauxoo/travis2docker' in dkr_content
