#!/bin/bash
{% for entrypoint in entrypoints %}
{{ entrypoint }}
{% endfor %}
