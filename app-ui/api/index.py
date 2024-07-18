from fastapi import FastAPI

import workflow as wf

workflow_store = wf.DataStore("workflow", data_model=wf.Workflow)

app = FastAPI()

@app.get("/api/python")
def hello_world():
    return {"message": "Hello World"}

@app.get("/api/workflows")
def list_workflows():
    workflows = workflow_store.scan()
    return {"workflows": workflows}