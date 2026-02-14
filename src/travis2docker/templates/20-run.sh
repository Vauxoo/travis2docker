#!/bin/bash
IMAGE={{ image }}
docker run {{ extra_params }} $IMAGE /entrypoint.sh
{{ extra_cmds }}
