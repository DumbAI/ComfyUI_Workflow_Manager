from .database import init_db, list_workflows, list_workflow_runs


if __name__ == "__main__":
    init_db()

    workflows = list_workflows()
    for workflow in workflows:
        print(f'[INFO] Workflow: {workflow}')

    workflow_runs = list_workflow_runs(lambda v: True)
    for workflow_run in workflow_runs:
        print(f'[INFO] Workflow run: {workflow_run}')