
import sys
import unittest

from travis2docker.travis2docker import main as t2d_main
from travis2docker.travis2docker import travis


class MainTest(unittest.TestCase):
    def setUp(self):
        self.repo_test = 'https://github.com/vauxoo-dev/fast-travis-test.git'
        self.branch_test = 'fast-travis-oca'

    def test_10_t2d(self):
        '''Test travis2docker first time'''
        sys.argv = [
            'travis2docker', self.repo_test, self.branch_test,
            '--root-path=/tmp/t2d_tests',
        ]
        t2d_main()

    def test_20_t2d(self):
        '''Test travis2docker second time'''
        sys.argv = [
            'travis2docker', self.repo_test, self.branch_test,
            '--root-path=/tmp/t2d_tests',
        ]
        t2d_main()

    def test_30_t2d_bash(self):
        '''Test travis2docker with bash script output'''
        travis_obj = travis(
            self.repo_test, self.branch_test,
            command_format='bash', docker_user='t2d_test',
            default_docker_image='t2d_test')
        travis_obj.get_travis2docker()

    def test_40_t2d_remotes(self):
        '''Test travis2docker remotes'''
        travis_obj = travis(
            self.repo_test, self.branch_test,
            command_format='docker', docker_user='t2d_test',
            default_docker_image='t2d_test',
            remotes=['moylop260', 'vauxoo-dev'])
        travis_obj.get_travis2docker()

    def test_t2d_build_extra_args(self):
        ''' Verify no error is thrown when extra-build-args are supplied '''
        sys.argv = [
            'travis2docker', self.repo_test, self.branch_test,
            '--root-path=/tmp/t2d_tests',
            '--build-extra-args="--disable-content-trust=true"',
        ]
        t2d_main()
