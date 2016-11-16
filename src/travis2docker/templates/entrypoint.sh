#!/bin/bash
{% if image == 'quay.io/travisci/travis-python' -%}
source /home/travis/virtualenv/python2.7_with_system_site_packages/bin/activate
{%- endif %}
source /usr/local/rvm/scripts/rvm
{% for entrypoint in entrypoints %}
{{ entrypoint }}
{% endfor %}
