from fastapi import FastAPI

import workflow as wf

# connect to the database
wf.init_db()


app = FastAPI()

@app.get("/api/python")
def hello_world():
    return {"message": "Hello World"}

@app.get("/api/workflows")
def list_workflows():
    workflows = wf.list_workflows()    
    return {"workflows": workflows}


@app.post("/api/workflows/{workflow_id}/run")
def launch_workflow(workflow_id: str):
    workflow_record_to_run = wf.get_workflow_by_id(workflow_id)
    workflow_to_run = wf.get_workflow_manifest(workflow_record_to_run.workflow_dir)
    runner = wf.ComfyUIProcessRunner(workflow_to_run)
    runner.setup()

    # TODO: load the workflow_api.json
    # runner.run()
    return {
        "port": runner.port
        }