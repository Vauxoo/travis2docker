FROM {{ image  }}
ADD {{ entrypoint_path }} /entrypoint.sh
RUN chown -R {{ user }}:{{ user }} /entrypoint.sh
ENV HOME=
{%- if user == 'root' -%}
/root
{%- else -%}
/home/{{ user }}
{%- endif %}

{% if image == 'quay.io/travisci/travis-python' -%}
ENV PATH=${PATH}:/home/travis/.nvm/v0.10.36/bin:/home/travis/.nvm/v0.10.36/lib/node_modules/npm/bin
{%- endif %}

{%- for src, dest in copies %}
ADD {{ src }} {{ dest }}
RUN chown -R {{ user }}:{{ user }} {{dest}}
{% endfor -%}

{% if sources -%}
RUN \
{% for source in sources %}
{{ source }} && \
{% endfor -%}
  echo "sources loaded"
{%- endif %}

{% if packages -%}
RUN apt-get update && apt-get install \
{%- for package in packages %}
  {{ package }} \
{% endfor -%}
  && echo "packages installed"
{%- endif %}

USER {{ user }}
ENV TRAVIS_REPO_SLUG={{ repo_owner }}/{{ repo_project }}
ENV TRAVIS_BUILD_DIR=${HOME}/build/${TRAVIS_REPO_SLUG}
RUN git init ${TRAVIS_BUILD_DIR} \
    && cd ${TRAVIS_BUILD_DIR} \
    && git remote add origin {{ project }} \
    && git fetch --update-head-ok -p origin \
{% if 'pull' in revision -%}
    '+refs/{{ revision }}/head:refs/{{ revision }}'
{%- else -%}
    '+refs/heads/{{ revision }}:refs/heads/{{ revision }}'
{%- endif %} \
    && git checkout -qf {{ revision }} \
    && git config --global user.email "{{ git_email }}" \
    && git config --global user.name "{{ git_user }}" \
{%- if remotes %}
{%- for remote in remotes %}
    && git remote add {{ remote }} git@github.com:{{ remote }}/{{ repo_project }}.git \
{%- endfor %}
{%- endif %}
    && echo 1  # TODO: Migrate to '&&'.join([for])

{% if add_self_rsa_pub -%}
RUN cat ${HOME}/.ssh/id_rsa.pub | tee -a ${HOME}/.ssh/authorized_keys
{%- endif %}

{% if env -%}
ENV {{ env }}
{%- endif %}

WORKDIR ${TRAVIS_BUILD_DIR}

{%- for run in runs %}
{% if image == 'quay.io/travisci/travis-python' -%}
RUN /bin/bash -c "source $HOME/virtualenv/python2.7_with_system_site_packages/bin/activate && {{ run }}"
{% else %}
RUN {{ run }}
{%- endif %}
{%- endfor %}
ENTRYPOINT /entrypoint.sh
