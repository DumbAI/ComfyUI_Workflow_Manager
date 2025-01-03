""" Manage workflow execution as state machine. 
    - Workflow is associated with runtime workspace containing preloaded models and modules
    - Workflow execution generate runtime data and logs that are stored in workspace
"""

from datetime import datetime
from .dao import Workspace, reconstruct_workflow, reconstruct_inventory, get_workflow_manifest
from .controller import run_workflow
from .database import *


def install_workflow(workspace_base_path: str, workflow_base_path: str):
    # 
    # Workflow installation
    #
    
    # Workflow pre-requisite files
    # - workflow.json // for backup an reuse
    # - workflow_api.json
    # - input_override.json
    # - dependency.json
    # - input/

    # base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
    workspace = Workspace(base_path=workspace_base_path)
    inventory = reconstruct_inventory(workspace_base_path)

    
    # Assume an app is installed in this path, below is the installation logic
    #
    # TODO: add records in database
    # workflow_base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflows/sticker"
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
    # workflow_record_to_run = get_workflow_by_id(worflow_record.id) # workflow metadata
    # run_workflow(workspace, workflow_record_to_run)

if __name__ == "__main__":
    install_workflow(
        workflow_base_path="/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflows/general_v1",
        workspace_base_path="/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
    )
