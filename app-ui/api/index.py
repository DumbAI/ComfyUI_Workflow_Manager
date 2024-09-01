from fastapi import FastAPI

import workflow as wf

# connect to the database
wf.init_db()


app = FastAPI()

@app.get("/api/workflows")
def list_workflows():
    workflows = wf.list_workflows()    
    return {"workflows": workflows}


@app.post("/api/workflows/{workflow_id}/run")
def launch_workflow(workflow_id: str):
    # Get workflow metadata from database
    workflow_record_to_run = wf.get_workflow_by_id(workflow_id)

    # Get workflow manifest from the workflow directory
    workflow_to_run = wf.get_workflow_manifest(workflow_record_to_run.workflow_dir)

    # Start workflow process runner
    runner = wf.ComfyUIProcessRunner(workflow_to_run)
    runner.setup()

    # TODO: load the workflow_api.json
    # runner.run()
    result = {
        "run_id": runner.run_id,
        "host": '100.112.4.55', # FIXME: a placeholder
        "port": runner.port
    }
    print(f'Running workflow: {result}')

    return result


@app.delete("/api/workflows/{workflow_id}/run/{run_id}")
def launch_workflow(workflow_id: str, run_id: str):
    workflow_record_to_run = wf.get_workflow_by_id(workflow_id)
    workflow_to_run = wf.get_workflow_manifest(workflow_record_to_run.workflow_dir)
    runner = wf.ComfyUIProcessRunner(workflow_to_run)
    runner.setup()

    # TODO: load the workflow_api.json
    # runner.run()

    return {
        "run_id": runner.run_id,
        "port": runner.port
    }