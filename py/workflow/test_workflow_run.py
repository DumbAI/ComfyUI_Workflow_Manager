""" Manage workflow execution as state machine. 
    - Workflow is associated with runtime workspace containing preloaded models and modules
    - Workflow execution generate runtime data and logs that are stored in workspace
"""
import json
from datetime import datetime
from .dao import Workspace, reconstruct_workflow, reconstruct_inventory, get_workflow_manifest
from .controller import run_workflow
from .database import *


def test_workflow_run():

    base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
    workspace = Workspace(base_path=base_path)
    inventory = reconstruct_inventory(base_path)

    # 
    # Workflow installation
    # Assume an app is installed in this path, below is the installation logic
    #
    workflow_base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflows/general_v1"
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
    workflow_record_to_run = get_workflow_by_id(worflow_record.id) # workflow metadata

    workflow_input_override_json_file = f'{workflow_record_to_run.workflow_dir}/input_override.json'
    # empty override, use default input from workflow
    input_override = {} 
    override_template = {}
    with open(workflow_input_override_json_file, 'r') as f:
        workflow_input_override_json = json.load(f)
        
        # override value using parameters from request
        override_value = workflow_input_override_json.get('override_value', {})
        override_value.update(input_override)
        
        # interpolate override value into override template
        override_template=workflow_input_override_json.get('override_template', {})
        # recursively update the input value in override template
        def update_input_value(override_value, override_template):
            for k, v in override_template.items():
                if isinstance(v, dict):
                    update_input_value(override_value, v)
                else:
                    if v in override_value:
                        override_template[k] = override_value[v]
        update_input_value(
            override_value, 
            override_template
        )
    run_workflow(
        workspace, workflow_record_to_run,
        input_override=override_template
    )


if __name__ == "__main__":
    test_workflow_run()
