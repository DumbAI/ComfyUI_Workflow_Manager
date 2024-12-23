#!/bin/bash

WORKDIR=/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/py

cd $WORKDIR

# VIRTUAL_ENV=/home/ruoyu.huang/workspace/xiaoapp/venv
# source $VIRTUAL_ENV/bin/activate

# source and export the environment variables from .env file
export $(cut -d= -f1- .env)

# run the python script
${VIRTUAL_ENV}/bin/python3 -m workflow.scheduler
