#!/bin/bash
export IMAGE={{ image }}
docker run {{ extra_params }} $1 $IMAGE $2
{{ extra_cmds }}
