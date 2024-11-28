#!/bin/bash

# source and export the environment variables from .env file
export $(cut -d= -f1- .env)

# run the python script
python3 -m workflow.scheduler
