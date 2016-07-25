FROM {{ image  }}
ADD {{ entrypoint_path }} /entrypoint.sh
ENV HOME={% if user == 'root' %}/root{% else %}/home/{{ user }}{% endif %}
{% for new_dir in new_dirs %}RUN mkdir -p {{ new_dir }} && chown {{ user }}:{{ user }} {{ new_dir }}{% endfor %}
{% for src, dest in copies %}ADD {{ src }} {{ dest }}
RUN chown -R {{ user }}:{{ user }} {{dest}}
{% endfor %}
USER {{ user }}
ENV TRAVIS_REPO_SLUG={{ repo_owner }}/{{ repo_project }}
ENV TRAVIS_BUILD_DIR=${HOME}/${TRAVIS_REPO_SLUG}
RUN git init ${TRAVIS_BUILD_DIR} \
    && cd ${TRAVIS_BUILD_DIR} \
    && git remote add origin git@github.com:${TRAVIS_REPO_SLUG}.git \
    # && git fetch --update-head-ok -p origin \
# {% if 'pull' in revision %}+refs/{{ revision }}/head:refs/{{ revision }}
# {% else %}'+refs/heads/{{ revision }}:refs/heads/{{ revision }}
# {% endif %}
    && git config --global user.email "{{ git_email }}" \
    && git config --global user.name "{{ git_user }}" \
{% if remotes %}
{% for remote in remotes %}&& git remote add {{ remote }} git@github.com:{{ remote }}/{{ repo_project }}.git \
{% endfor %}
{% endif %}
   && echo 1  # TODO: Migrate to '&&'.join([for])
{% if add_self_rsa_pub %}RUN cat ${HOME}/.ssh/id_rsa.pub | tee -a ${HOME}/.ssh/authorized_keys {% endif %}
{% if env %}ENV {{ env }}{% endif %}
WORKDIR ${TRAVIS_BUILD_DIR}
{% for run in runs %}# RUN {{ run }} {% endfor %}
ENTRYPOINT /entrypoint.sh
