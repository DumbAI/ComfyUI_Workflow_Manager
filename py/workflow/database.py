# ORM layer
from enum import Enum
from typing import List
from sqlmodel import SQLModel, Field, create_engine, Session, select
import os
from pydantic import computed_field
from sqlalchemy import JSON

# TODO: pointing to the workflow.db on the workspace
DATABASE_URL = "sqlite:////home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflow.db"
engine = create_engine(DATABASE_URL, echo=True)

class WorkflowRecord(SQLModel, table=True):
    # a record of a workflow in database
    # only store the metadata of a workflow

    id: int = Field(primary_key=True)
    name: str
    created_at: str
    workflow_dir: str
    description: str | None = None
    updated_at: str | None = None

class WorkflowRunStatus(Enum):
    # status of a workflow run
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    FAILED = "failed"




class WorkflowRunRecord(SQLModel, table=True):
    # a record of a workflow run in database
    id: int = Field(primary_key=True)
    workflow_id: int # foreign key to WorkflowRecord

    status: str
    created_at: str
    updated_at: str | None = None

    # Workflow inputs
    input_files_json: str | None = None # file name -> file path
    input_override_json: str | None = None

    # 
    # Runtime metadata, created after handshake with the workflow run process
    #
    runtime_dir: str | None = '.' # the runtime directory of the workflow run, input, output and log files are stored here
    # metadata, used to connect to the workflow run process
    host: str | None = None
    port: int | None = None


    @computed_field
    def input_dir(self) -> str:
        return os.path.join(self.runtime_dir, "input")

    @computed_field
    def output_dir(self) -> str:
        return os.path.join(self.runtime_dir, "output")

    # temp dir
    @computed_field
    def temp_dir(self) -> str:
        return os.path.join(self.runtime_dir, "temp")
    
    @computed_field
    def log_file(self) -> str:
        return os.path.join(self.runtime_dir, "workflow_run.log")


def init_db():
    SQLModel.metadata.create_all(engine)


def list_workflows():
    with Session(engine) as session:
        stmt = select(WorkflowRecord)
        workflows = session.exec(stmt)

        results = []
        for workflow in workflows:
            print(workflow)
            results.append(workflow)
        return results


def get_workflow_by_id(workflow_id: int):
    with Session(engine) as session:
        workflow = session.get(WorkflowRecord, workflow_id)
        print(workflow)
        return workflow


def create_workflow(workflow_record: WorkflowRecord):
    with Session(engine) as session:
        session.add(workflow_record)
        session.commit()
        session.refresh(workflow_record)
        print(f"Workflow created: {workflow_record}")

def create_workflow_run(workflow_run_record: WorkflowRunRecord):
    with Session(engine) as session:
        session.add(workflow_run_record)
        session.commit()
        session.refresh(workflow_run_record)

def update_workflow_run(workflow_run_record: WorkflowRunRecord):
    with Session(engine) as session:
        session.add(workflow_run_record)
        session.commit()
        session.refresh(workflow_run_record)

def scan_workflow_runs(filter_fn):
    with Session(engine) as session:
        stmt = select(WorkflowRunRecord)
        workflow_runs = session.exec(stmt)
        results = []
        for workflow_run in workflow_runs:
            if filter_fn(workflow_run):
                results.append(workflow_run)
        return results

