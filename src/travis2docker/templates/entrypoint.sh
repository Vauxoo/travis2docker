#!/bin/bash
{% if image == 'quay.io/travisci/travis-python' -%}
source /home/travis/virtualenv/python{{ python_version }}/bin/activate
{% elif  image == 'vauxoo/odoo-80-image-shippable-auto' -%}
source ${REPO_REQUIREMENTS}/virtualenv/python{{ python_version }}/bin/activate && source ${REPO_REQUIREMENTS}/virtualenv/nodejs/bin/activate
{%- endif %}
source /rvm_env.sh
{% for entrypoint in entrypoints %}
{{ entrypoint }}
{% endfor %}
