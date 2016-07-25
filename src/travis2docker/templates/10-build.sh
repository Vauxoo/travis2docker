#!/bin/bash
export IMAGE={{ image }}
docker build {{ extra_params }} $1 -t $IMAGE {{ dirname_dockerfile }}
{{ extra_cmds }}
