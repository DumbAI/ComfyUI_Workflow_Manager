""" Manage workflow execution as state machine. 
    - Workflow is associated with runtime workspace containing preloaded models and modules
    - Workflow execution generate runtime data and logs that are stored in workspace
"""

from datetime import datetime
from typing import Dict
import json

from .dao import Workspace, reconstruct_workflow, reconstruct_inventory, get_workflow_manifest
from .controller import ComfyUIRunner
from .utils import logger


from .database import *


def launch_workflow():

    base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
    workspace = Workspace(base_path=base_path)
    inventory = reconstruct_inventory(base_path)

    # 
    # Workflow installation
    # Assume an app is installed in this path, below is the installation logic
    #
    # TODO: add records in database
    workflow_base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflows/sticker"
    workflow = reconstruct_workflow(workflow_base_path)
    # Expand workflow into a workspace
    # Write the workflow manifest to workspace
    workflow.prepare_workspace(inventory)

    # Write the workflow metadata to database
    init_db()
    worflow_record = WorkflowRecord(
        name=workflow.name, 
        workflow_dir=workflow.workflow_dir,
        created_at=datetime.now().isoformat(),
        description=workflow.description)
    create_workflow(worflow_record)


    # 
    # Run the workflow
    #
    # workflow metadata
    workflow_record_to_run = get_workflow_by_id(worflow_record.id)
    # workflow manifest
    workflow_to_run = get_workflow_manifest(workflow_record_to_run.workflow_dir)

    # 
    # Launch the workflow process
    # TODO: create workflow run record in DB
    input_override = {
        "326": {
            "inputs": {
                "image": "headshot.png"
            }
        },
    }
    workflow_run = WorkflowRunRecord(
        workflow_id=workflow_record_to_run.id,
        status=WorkflowRunStatus.PENDING.value,
        created_at=datetime.now().isoformat(),
        # TODO: input files should points to folder on the workspace, relative to 'user_space' folder
        input_files_json=json.dumps({"headshot.png": "taylor-swift.jpeg"}),
        input_override_json=json.dumps(input_override)
    )
    create_workflow_run(workflow_run)

    # scan workflow_run queue, and launch workflow process
    pending_workflow_runs = scan_workflow_runs(lambda v: v.status == WorkflowRunStatus.PENDING.value)
    for run in pending_workflow_runs:
        logger.info(f"Launching workflow run: {run.id}")
        runner = ComfyUIRunner(
            workspace=workspace,
            workflow=workflow_to_run,
            workflow_run=run,
            callback=update_workflow_run
            )
        runner.setup()
        runner.run()
    
        breakpoint()
        runner.teardown()


if __name__ == "__main__":
    launch_workflow()
