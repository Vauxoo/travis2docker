[![Coverage Status](https://coveralls.io/repos/Vauxoo/travis2docker/badge.svg?branch=master&service=github)](https://coveralls.io/github/Vauxoo/travis2docker?branch=master)
[![Build Status](https://travis-ci.org/Vauxoo/travis2docker.svg?branch=master)](https://travis-ci.org/Vauxoo/travis2docker)
[![PyPi version](https://img.shields.io/pypi/v/travis2docker.svg)](https://pypi.python.org/pypi/travis2docker)
[![PyPi downloads](https://img.shields.io/pypi/dm/travis2docker.svg)](https://pypi.python.org/pypi/travis2docker)



# travis2docker

Script to generate Dockerfile from .travis.yml file

## Install

### From pipy
`# pip install travis2docker`

### local source
```bash
$ git clone https://github.com/Vauxoo/travis2docker.git
$ cd travis2docker
# pip install .
```

### From remote source
`# pip install git+https://github.com/Vauxoo/travis2docker.git`

## Usage
 `travisfile2dockerfile REPO_URL BRANCH`
 
 Or with pull request
 `travisfile2dockerfile REPO_URL pull/##`
 
 In REPO_URL use the ssh url of github.

 For more information execute:
 `travisfile2dockerfile --help`
 
 Example:
 ```bash
 travisfile2dockerfile --root-path=$HOME/t2d git@github.com:Vauxoo/forecast.git 8.0
 ```
 The output is:
 ```bash
 Script generated:
${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/1
${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/2
```
The first one is the build for env with tests server, the second one is for env with lint tests.

To build the image is with
`${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/1/10-build.sh`

To create a container is with
`${HOME}/t2d/script/git_github.com_Vauxoo_forecast.git/8.0/1/20-run.sh --entrypoint=bash`

To run the test (into of container):
`/entrypoint.sh`

## Depends

### SSH key without password

Dockerfile don't support a prompt to entry your password, then you need remove it.

```bash
export fname=~/.ssh/id_rsa
cp ${fname} ${fname}_with_pwd
openssl rsa -in ${fname} -out ${fname}_without_pwd
cp ${fname}_without_pwd ${fname}
```

### Download the big image

Docker use a image with many packages pre-installed.

`docker pull vauxoo/odoo-80-image-shippable-auto`

Note: You can define a custom image to use with `--docker-image` parameter.


### Install docker

https://docs.docker.com/installation/ubuntulinux/
