# ORM layer

from sqlmodel import SQLModel, Field, create_engine, Session, select

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


class WorkflowRunRecord(SQLModel, table=True):
    # a record of a workflow run in database
    id: int = Field(primary_key=True)
    workflow_id: int
    status: str
    created_at: str
    updated_at: str | None = None

    # metadata, used to monitor and shutdown the workflow run process
    host: str | None = None
    port: int | None = None
    

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
