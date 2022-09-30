#!/usr/bin/env bash

service_postgres_without_sudo(){
    USER="${1}"
    PASSWORD="${2}"
    VERSIONS=$(pg_lsclusters  | sed '1d' | awk '{print $1}' )
    for version in $VERSIONS; do
        pg_dropcluster --stop $version main
    done
    adduser ${USER} postgres
    chown -R ${USER}:postgres /var/run/postgresql
    for version in $VERSIONS; do
        pg_createcluster -u ${USER} -g postgres -s /var/run/postgresql -p 15432 --lc-collate=${LC_COLLATE} --start-conf auto --start $version main
        echo "include = '/etc/postgresql-common/common-vauxoo.conf'" >> /etc/postgresql/$version/main/postgresql.conf
        su - ${USER} -c "psql -p 15432 -d postgres -c  \"ALTER ROLE ${USER} WITH PASSWORD '${PASSWORD}';\""
        su - ${USER} -c "psql -p 15432 -d postgres -c  \"CREATE ROLE postgres LOGIN SUPERUSER INHERIT CREATEDB CREATEROLE;\""
        /etc/init.d/postgresql stop $version
        sed -i "s/port = 15432/port = 5432/g" /etc/postgresql/$version/main/postgresql.conf
    done
}

install_pgcli_venv(){
    # pgcli==3.1.0 change psycopg2 version
    virtualenv /venev-pgcli
    . /venev-pgcli/bin/activate
    pip install pgcli
    echo 'alias pgcli2="source /venev-pgcli/bin/activate && pgcli -l"' >> $PROFILE_FILE
}

odoo_conf(){
    export ODOO_CONF=/home/odoo/.openerp_serverrc
    /entry_point.py run true
    sed -i '/db_host\|db_password\|db_user/d' $ODOO_CONF
    su odoo -c "mkdir -p $ODOORC_DATA_DIR"
}

custom_alias(){
    cat >> /etc/bash.bashrc << EOF
alias psql_logs_enable="export PGOPTIONS=\" -c client_min_messages=notice -c log_min_messages=warning -c log_min_error_statement=error -c log_min_duration_statement=0 -c log_connections=on -c log_disconnections=on -c log_duration=off -c log_error_verbosity=verbose -c log_lock_waits=on -c log_statement=none -c log_temp_files=0\""
alias psql_logs_disable="unset PGOPTIONS"
alias tail2="multitail -cS odoo"
alias rgrep="rgrep -n"
git_fetch_pr() {
  REMOTE=$1
  shift 1
  git fetch -p $REMOTE +refs/pull/*/head:refs/pull/$REMOTE/*
}
git_fetch_mr() {
  REMOTE=$1
  shift 1
  # git fetch -p $REMOTE +refs/merge_requests/*/head:refs/pull/$REMOTE/*
  git fetch -p $REMOTE +refs/merge-requests/*/head:refs/pull/$REMOTE/*
}
EOF
    # alias odoo
}

# You can add new packages here
install_dev_tools(){
    apt update -qq
    # TODO: Download a versioned public file?
    apt install -y \
        sudo \
        tree \
        iputils-ping \
        expect-dev \
        tcl8.6 \
        less \
        openssh-server \
        pgbadger \
        p7zip-full mosh bpython \
        rsync \
        gettext \
        net-tools \
        libecpg-dev \
        iproute2
        # aspell aspell-en aspell-es \
        # emacs \
        # byobu \
        # multitail  # Set the terminal with red letters build the docker

    sudo pip install -q \
        ipython \
        py-spy \
        virtualenv \
        ipdb \
        pre-commit-vauxoo \
        diff-highlight \
        pg-activity \
        nodeenv \
        pdbpp
    # pre install pre-commit-vauxoo?
    # sudo su odoo -c "git init /tmp/test && cd /tmp/test && pre-commit-vauxoo -f"
    touch /home/odoo/full_test-requirements.txt
    sudo pip install -r /home/odoo/full_test-requirements.txt

    # Keep alive the ssh server
    #   60 seconds * 360 = 21600 seconds = 6 hours
    # https://www.bjornjohansen.no/ssh-timeout
    echo "ClientAliveInterval 60" >> /etc/ssh/sshd_config
    echo "ClientAliveCountMax 360" >> /etc/ssh/sshd_config

    # Install ngrok
    wget -O /tmp/ngrok.tgz https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz && \
    tar xvzf /tmp/ngrok.tgz -C /usr/local/bin || true

    # Configure diff-highlight on git after install
    cat >> /etc/gitconfig << EOF
[pager]
    log = diff-highlight | less
    show = diff-highlight | less
    diff = diff-highlight | less
EOF
    cat >> /etc/multitail.conf << EOF
# Odoo log
colorscheme:odoo
cs_re:blue:^[0-9]*-[0-9]*-[0-9]* [0-9]*:[0-9]*:[0-9]*,[0-9]*
cs_re_s:blue,,bold:^[^ ]* *[^,]*,[^ ]* *[0-9]* *(DEBUG) *[^ ]* [^ ]* *(.*)$
cs_re_s:green:^[^ ]* *[^,]*,[0-9]* *[0-9]* *(INFO) *[^ ]* [^ ]* *(.*)$
cs_re_s:yellow:^[^ ]* *[^,]*,[0-9]* *[0-9]* *(WARNING) *[^ ]* [^ ]* *(.*)$
cs_re_s:red:^[^ ]* *[^,]*,[0-9]* *[0-9]* *(ERROR) *[^ ]* [^ ]* *(.*)$
cs_re_s:red,,bold:^[^ ]* *[^,]*,[0-9]* *[0-9]* *(CRITICAL) *[^ ]* [^ ]* *(.*)$
EOF

    # Configure emacs for odoo user
    git clone --depth 1 -b master https://github.com/Vauxoo/emacs.d.git /home/odoo/.emacs.d
    chown -R odoo:odoo /home/odoo/.emacs.d

    # TODO: Install custom vim?
}

bash_colorized(){
    cat >> ~/.bashrc << 'EOF'
Purple="\[\033[0;35m\]"
BIPurple="\[\033[1;95m\]"
Color_Off="\[\033[0m\]"
PathShort="\w"
UserMachine="$BIPurple[\u@$Purple\h]"
GREEN_WOE="\001\033[0;32m\002"
RED_WOE="\001\033[0;91m\002"
git_ps1_style(){
    local git_branch="$(__git_ps1 2>/dev/null)";
    local git_ps1_style="";
    if [ -n "$git_branch" ]; then
        if [ -n "$GIT_STATUS" ]; then
            (git diff --quiet --ignore-submodules HEAD 2>/dev/null)
            local git_changed=$?
            if [ "$git_changed" == 0 ]; then
                git_ps1_style=$GREEN_WOE;
            else
                git_ps1_style=$RED_WOE;
            fi
        fi
        git_ps1_style=$git_ps1_style$git_branch
    fi
    echo -e "$git_ps1_style"
}
PS1=$UserMachine$Color_Off$PathShort\$\\n"\$(git_ps1_style)"$Color_Off\$" "
EOF
}

git_set_remote(){
    (su odoo -c "cd /home/odoo/build && python3 -c \"import build;build.git_set_remote()\"")
}

chown_all(){
    find /home/odoo -maxdepth 1 -user root -exec chown odoo:odoo -R {} \;
    chown -R odoo:odoo /etc/postgresql-common/common-vauxoo.conf
}

configure_zsh(){
    # TODO: Add arg to install zsh
    # Call this method with "apt update" before
    apt install -y zsh
    wget -O /tmp/install_zsh.sh https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh && \
        chmod +x /tmp/install_zsh.sh
    sh /tmp/install_zsh.sh "" --unattended
    cp -r /root/.oh-my-zsh /home/odoo
    wget -O /home/odoo/.oh-my-zsh/themes/odoo-shippable.zsh-theme https://gist.githubusercontent.com/schminitz/9931af23bbb59e772eec/raw/cb524246fc93df242696bc3f502cababb03472ec/schminitz.zsh-theme
    cp /root/.zshrc /home/odoo/.zshrc
    chown -R odoo:odoo /home/odoo/.oh-my-zsh /home/odoo/.zshrc
    sed -i 's/root/home\/odoo/g' /home/odoo/.zshrc
    sed -i 's/robbyrussell/odoo-shippable/g' /home/odoo/.zshrc
    sed -i 's/^plugins=(/plugins=(\n  virtualenv\n/' /home/odoo/.zshrc
    # default using bash
    usermod -s /bin/bash root
    usermod -s /bin/bash odoo
}
