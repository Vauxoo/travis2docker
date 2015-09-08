
import setuptools


setuptools.setup(setup_requires=['pbr'],
                 pbr=True,
                 test_suite="travis2docker.test",
                 package_data={'': ['*.yaml']})
