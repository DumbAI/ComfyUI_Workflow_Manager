# Development thesis

An open source framework to manage and run AI native workflows. 

The framework is easy to use on home laptops (Mac, Windows), also easy to deploy to kubenete cluster and be used in a production environment.

The framework should use existing building block, primarily ComfyUI, to offer low-code app building experience.

The framework should expand ComfyUI and offer building blocks to build AI native App for text, doc and audio processing.

The framework should make it easy to package and distribute via an app store.

The framework should offer native eval components for AI app (validation, human review, accuracy dashboard)

The framework should able to run workflow in two mode: mutable (interactive) and immutable

The framework should run workflows in parallel, and manage a worker pool

The framework should be able to run workflow in remote machine (how??? Skypilot?)

The framework UI should show status of all worker, including CPU, GPU, Mem utilization


# Work with workspace

sqlite3 your_database.db

```
.tables

select * from workflowrecord;

.quit
```


## Service tab

Service tab:

```
[Unit]
Description=ComfyUI Workflow Manager Service
After=network.target

[Service]
Type=simple
User=ruoyu.huang
WorkingDirectory=/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/py
Environment="PATH=/home/ruoyu.huang/workspace/xiaoapp/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="VIRTUAL_ENV=/home/ruoyu.huang/workspace/xiaoapp/venv"
EnvironmentFile=/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/py/.env
ExecStart=/home/ruoyu.huang/workspace/xiaoapp/venv/bin/python3 -m workflow.scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Install service tab
```
sudo vi /etc/systemd/system/comfyui-workflow-manager.service
sudo chmod 644 /etc/systemd/system/comfyui-workflow-manager.service
sudo systemctl enable comfyui-workflow-manager
sudo systemctl start comfyui-workflow-manager

sudo systemctl status comfyui-workflow-manager
```

Monitor the logs

```
journalctl -u comfyui-workflow-manager -f
```


### Install New Workflow

Copy pre-requisite file to workflow folder
 - workflow.json // for backup an reuse
 - workflow_api.json
 - input_override.json
 - dependency.json
 - input/

 Carefully create the input_override.json
 - pick the node from workflow_api.json
 - change node input value to a symbol
 - provide default value for all input symbols

 Then copy input files (text, image) to input/ folder, 
 and make sure deafault value in input_override.json match the file name in input/ folder

 run workflow installer to install the workflow into database
 ```
 python -m workflow.workflow_installer
 ```

 Or run the workflow test to test the workflow ()
 ```
 python -m workflow.test_workflow_run
 ```