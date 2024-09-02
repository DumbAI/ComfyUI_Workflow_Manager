from .database import init_db, scan_workflow_runs


if __name__ == "__main__":
    init_db()
    workflow_runs = scan_workflow_runs(lambda v: True)
    for workflow_run in workflow_runs:
        print(f'Workflow run: {workflow_run}')