""" Manage workflow execution as state machine. 
    - Workflow is associated with runtime workspace containing preloaded models and modules
    - Workflow execution generate runtime data and logs that are stored in workspace
"""

from pydantic import BaseModel

from .in_mem_store import DataStore
from .db import reconstruct_workflow, reconstruct_inventory
from .controller import ComfyUIProcessRunner
from .utils import logger

class WorkflowScheduler:
    def __init__(self, workflow_db: DataStore, workflow_run_db: DataStore):
        self.workflow_db = workflow_db
        self.workflow_run_db = workflow_run_db
        self.run_registry = {}

    def schedule(self, workflow_id: str) -> None:
        workflow = self.workflow_db.get(workflow_id)
        assert workflow is not None
        

        workflow_run = self.workflow_run_db.scan(lambda k, v: v.workflow_id == workflow_id)[0]
        assert workflow_run is not None
        logger.info(f"Workflow: {workflow}")
        logger.info(f"Workflow Run: {workflow_run}")

        # Create runner
        runner = ComfyUIProcessRunner(workflow, workflow_run)
        self.run_registry[workflow_run.id] = runner
        logger.info(f"Starting workflow run: {workflow_run.id}")
        runner.setup()
        # time.sleep(60)
        runner.run()
        logger.info(f"Terminating workflow run: {workflow_run.id}")
        runner.teardown()



def launch_workflow():
    # launch a workflow interactively

    base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
    inventory = reconstruct_inventory(base_path)
    workflow_base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflows/all_in_one_controlnet"
    workflow = reconstruct_workflow(workflow_base_path)
    workflow.prepare_workspace(inventory)
    runner = ComfyUIProcessRunner(workflow)
    runner.setup()

    breakpoint()
    runner.teardown()


if __name__ == "__main__":
    launch_workflow()
