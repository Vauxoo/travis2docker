#!/bin/bash
export IMAGE={{ image }}
# Run detached so we capture the exact container id; we re-attach below unless the caller
# asked for a detached run (-d/--detach), in which case we just print the id like docker run.
CONTAINER=$(docker run {{ extra_params }} $1 -ditP $IMAGE $2)

# Some files under /home/odoo end up owned by root or other users (declared VOLUMEs and
# files shared into the container); fix their ownership in the background so we can attach ASAP.
docker exec --user=root "$CONTAINER" find /home/odoo -maxdepth 2 -not -user odoo -exec chown -R odoo:odoo {} + &

# Detach intent: a single-dash cluster holding a d (-d, -dit, -itd...) or --detach.
detach_re='[[:space:]](-[a-zA-Z]*d[a-zA-Z]*|--detach)[[:space:]]'
if [[ " {{ extra_params }} $1 " =~ $detach_re ]]; then
    wait
    echo "$CONTAINER"
else
    docker attach "$CONTAINER"
fi
{{ extra_cmds }}
