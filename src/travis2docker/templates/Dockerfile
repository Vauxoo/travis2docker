FROM {{ image  }}
COPY {{ entrypoint_path }} /entrypoint.sh
RUN chown -R {{ user }}:{{ user }} /entrypoint.sh
COPY {{ rvm_env_path }} /rvm_env.sh
RUN chown -R {{ user }}:{{ user }} /rvm_env.sh
ENV HOME=
{%- if user == 'root' -%}
/root
{%- else -%}
/home/{{ user }}
{%- endif %}

{% if image == 'quay.io/travisci/travis-python' -%}
ENV PATH=${PATH}:/home/travis/.nvm/v0.10.36/bin:/home/travis/.nvm/v0.10.36/lib/node_modules/npm/bin
{%- endif %}

{%- for src, dest in copies or [] %}
COPY {{ src }} {{ dest }}
RUN chown -R {{ user }}:{{ user }} {{dest}}
{% endfor -%}

{% if sources -%}
RUN {{ ' && '.join(sources)  }}
{%- endif %}

{% if packages -%}
RUN apt-get update; apt-get install {{ ' '.join(packages) }}
{%- endif %}

USER {{ user }}
ENV TRAVIS_REPO_SLUG={{ repo_owner }}/{{ repo_project }}
ENV TRAVIS_BUILD_DIR=${HOME}/build/${TRAVIS_REPO_SLUG}
RUN git init ${TRAVIS_BUILD_DIR} \
    && cd ${TRAVIS_BUILD_DIR} \
    && git remote add origin {{ project }} \
    && git fetch --update-head-ok -p origin \
{% if revision.startswith('pull/') -%}
    '+refs/{{ revision }}/head:refs/{{ revision }}'
{%- else -%}
    '+refs/heads/{{ revision }}:refs/heads/{{ revision }}'
{%- endif %} \
    && git checkout -qf {{ revision }} \
    && git config --global user.email "{{ git_email }}" \
    && git config --global user.name "{{ git_user }}" \
{%- for remote in remotes or [] %}
    && git remote add {{ remote }} git@github.com:{{ remote }}/{{ repo_project }}.git \
{%- endfor %}
    && echo 1

{% if add_self_rsa_pub -%}
RUN cat ${HOME}/.ssh/id_rsa.pub | tee -a ${HOME}/.ssh/authorized_keys
{%- endif %}

{% if env -%}
ENV {{ env }}
{%- endif %}

WORKDIR ${TRAVIS_BUILD_DIR}


{% if runs -%}
{% if image == 'quay.io/travisci/travis-python' -%}
RUN /bin/bash -c "source $HOME/virtualenv/python2.7_with_system_site_packages/bin/activate && source /rvm_env.sh && {{ ' && '.join(runs) }}"
{% elif  image == 'vauxoo/odoo-80-image-shippable-auto' -%}
RUN /bin/bash -c "source ${REPO_REQUIREMENTS}/virtualenv/python2.7/bin/activate && source ${REPO_REQUIREMENTS}/virtualenv/nodejs/bin/activate && source /rvm_env.sh && {{ ' && '.join(runs) }}"
{% else %}
RUN /bin/bash -c "source /rvm_env.sh && {{ ' && '.join(runs) }}"
{%- endif %}
{%- endif %}
ENTRYPOINT /entrypoint.sh
