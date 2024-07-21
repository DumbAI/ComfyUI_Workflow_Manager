from pydantic import BaseModel, Field
import uuid

from typing import Optional, List, Tuple, Dict

from workflow.in_mem_store import DataStore


class Dir(BaseModel):
    """  encapsulates a directory
    """
    dir_path: str

class CodeRepo(BaseModel):
    """  encapsulates a remote code repo
    """
    github_url: str
    commit_sha: str
    branch: Optional[str] = None
    tag: Optional[str] = None

class EnvVars(BaseModel):
    """  encapsulates an env var
    """
    env_var_list: List[Tuple[str, str]] 

class BaseEnv(BaseModel):
    """  encapsulates the env (code, env var) for a workflow
    """
    pass


class PythonCondaEnv(BaseModel):
    conda_env_path: str
    main_code_repo: CodeRepo
    python_path: Optional[str] = None 
    env_vars: Optional[EnvVars] = None



class Workflow(BaseModel):
    id: Optional[str] = Field(default=None, primary_key=True)
    name: str
    description: str
    env: PythonCondaEnv
    load_model_dir: Dir
    input_dir: Optional[Dir] = None # default input folder for the workflow
    metadata_dir: Dir # metadata dir, e.g., workflow.json, workflow_api.json
    config: Dict = {} # workflow config, e.g., workflow.json, workflow_api.json

class WorkflowRun(BaseModel):
    id: Optional[str] = Field(default=None, primary_key=True)
    workflow_id: str
    status: str
    start_time: str
    end_time: str

    input_dir: Optional[Dir] = None # deprecated
    output_dir: Optional[Dir] = None
    workspace: Optional[Dir] = None # ComfyUI workspace
    status: Optional[str] = None


if __name__ == "__main__":
    workflow_1 = Workflow(
        id=str(uuid.uuid4()),
        name="workflow_1", 
        description="workflow 1", 
        env=PythonCondaEnv(conda_env_path="/home/ruoyu.huang/miniconda3/envs/xiaoapp", main_code_repo=CodeRepo(github_url="git@github.com:comfyanonymous/ComfyUI.git", commit_sha='4ca9b9cc29fefaa899cba67d61a8252ae9f16c0d', tag='v0.0.1')),
        load_model_dir=Dir(dir_path="/home/ruoyu.huang/workspace/xiaoapp/models"),
        metadata_dir=Dir(dir_path="/home/ruoyu.huang/workspace/xiaoapp/metadata")
    )

    

    workflow_db = DataStore("workflow", data_model=Workflow)
    workflow_db.put(workflow_1)
    # print(workflow_db.get(workflow_1.id))
    
    workflow_run_db = DataStore("workflow_run", data_model=WorkflowRun)
    workflow_run = WorkflowRun(
        id=str(uuid.uuid4()),
        workflow_id=workflow_1.id,
        status="running",
        start_time="2021-09-01 12:00:00",
        end_time="2021-09-01 12:01:00",
        output_dir=Dir(dir_path="/home/ruoyu.huang/workspace/xiaoapp/output"),
        log_dir=Dir(dir_path="/home/ruoyu.huang/workspace/xiaoapp/logs")
    )
    workflow_run_db.put(workflow_run)
    print(workflow_run_db.scan(lambda k, v: v.workflow_id == workflow_1.id))
