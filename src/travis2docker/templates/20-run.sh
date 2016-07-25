#!/bin/bash
export IMAGE={{ image }}
docker run {{ extra_params }} $1 -itP $IMAGE $2
{{ extra_cmds }}
