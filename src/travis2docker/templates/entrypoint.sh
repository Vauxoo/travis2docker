#!/bin/bash
{% if image == 'quay.io/travisci/travis-python' -%}
source /home/travis/virtualenv/python{{ python_version }}/bin/activate
{% elif  image == 'vauxoo/odoo-80-image-shippable-auto' -%}
# Compatibility with old images without virtualenv for each odoo version
ln -s ${REPO_REQUIREMENTS}/virtualenv/python{{ python_version }} ${REPO_REQUIREMENTS}/virtualenv/python{{ python_version }}${VERSION} || true
source ${REPO_REQUIREMENTS}/virtualenv/python{{ python_version }}${VERSION}/bin/activate && source ${REPO_REQUIREMENTS}/virtualenv/nodejs/bin/activate
{%- endif %}
source /rvm_env.sh
{% for entrypoint in entrypoints %}
{{ entrypoint }}
{% endfor %}
