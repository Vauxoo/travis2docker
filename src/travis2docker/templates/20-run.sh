#!/bin/bash
export IMAGE={{ image }}
CONTAINER=$(docker run {{ extra_params }} $1 -ditP $IMAGE $2)

# Some files under /home/odoo end up owned by root or other users (declared VOLUMEs and
# files shared into the container); fix their ownership in the background so we can attach ASAP
docker exec --user=root "$CONTAINER" find /home/odoo -maxdepth 2 -not -user odoo -exec chown -R odoo:odoo {} + &
docker attach "$CONTAINER"
{{ extra_cmds }}
