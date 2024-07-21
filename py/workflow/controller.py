""" Schedule the workflow execution
1) create or allocate a worker
2) assign a workflow to the worker
3) monitor the workflow execution, update run status
"""
import uuid
import os
import sys
import time
from datetime import datetime
import subprocess
import threading
from abc import ABC, abstractmethod

from workflow.in_mem_store import DataStore
from workflow.db import Workflow, WorkflowRun, Dir




class Runner(ABC):

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def teardown(self):
        pass


class ComfyUIProcessRunner(Runner):
    """ Run a ComfyUI workflow in a subprocess
    Reference: https://github.com/Comfy-Org/comfy-cli/blob/main/comfy_cli/command/launch.py
    """

    PROC_SHUTDOWN_TIMEOUT_SEC = 5

    def __init__(self, workflow: Workflow, workflow_run: WorkflowRun):
        self.workflow = workflow
        self.workflow_run = workflow_run

    def _launch_comfyui(self, extra):
        reboot_path = None

        session_path = self.workflow_run.session_dir.dir_path if self.workflow_run.session_dir is not None else f'/tmp/comfyui-workflow/{self.workflow_run.id}'
        if not os.path.exists(session_path):
            os.makedirs(session_path)

        log_file = os.path.join(session_path, "log")

        new_env = os.environ.copy()

        # session_path = os.path.join(
        #     ConfigManager().get_config_path(), "tmp", str(uuid.uuid4())
        # )
        # new_env["__COMFY_CLI_SESSION__"] = session_path
        new_env["PYTHONENCODING"] = "utf-8"

        # To minimize the possibility of leaving residue in the tmp directory, use files instead of directories.
        # self.reboot_path = os.path.join(session_path, ".reboot")

        extra = extra if extra is not None else []

        process = None

        try:
            with open(log_file, "w") as f:
                while True:
                    if sys.platform == "win32":
                        process = subprocess.Popen(
                            [sys.executable, "main.py"] + extra,
                            stdout=f,
                            stderr=f,
                            text=True,
                            env=new_env,
                            encoding="utf-8",
                            shell=True,  # win32 only
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # win32 only
                        )
                    else:
                        print(f"Running: {sys.executable} main.py {extra}")
                        process = subprocess.Popen(
                            [sys.executable, "main.py"] + extra,
                            text=True,
                            env=new_env,
                            encoding="utf-8",
                            stdout=f,
                            stderr=f,
                        )
                    return process
        except KeyboardInterrupt:
            if process is not None:
                os._exit(1)


    def setup(self):
        # TODO: setup run workspaces

        workspace = self.workflow_run.workspace.dir_path

        # run ComfyUI main process
        host = '127.0.0.1'
        port = '8188'
        # ComfyUI args
        args = [
            '--listen', host,
            '--port', port,
        ]
        
        os.chdir(workspace)
        self.process = self._launch_comfyui(args)
        # self.proc = subprocess.Popen(command, capture_output=True, capture_error=True)
        # subprocess.run(command, capture_output=True, capture_error=True)

    def run(self):
        pass

    def teardown(self):
        try:
            self.process.terminate()
            self.process.wait(timeout=ComfyUIProcessRunner.PROC_SHUTDOWN_TIMEOUT_SEC) # wait for 5 seconds
            returncode = self.process.poll()
            print(f"Process terminated with return code: {returncode}")
            if returncode is None:
                # process has not exit yet, force kill it
                self.process.kill()
        except Exception as e:
            print(f"Error terminating process: {e}. Force killing the process.")
            self.process.kill()


        # if reboot_path is None:
        #     print("[bold red]ComfyUI is not installed.[/bold red]\n")
        #     os._exit(process.pid)

        # if not os.path.exists(reboot_path):
        #     os._exit(process.pid)

        # os.remove(reboot_path)

        return 

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
        print(f"Workflow: {workflow}")
        print(f"Workflow Run: {workflow_run}")

        runner = ComfyUIProcessRunner(workflow, workflow_run)
        self.run_registry[workflow_run.id] = runner
        print(f"Starting workflow run: {workflow_run.id}")
        runner.setup()
        time.sleep(60)
        print(f"Terminating workflow run: {workflow_run.id}")
        runner.teardown()



if __name__ == "__main__":
    workflow_db = DataStore("workflow", data_model=Workflow, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    workflow_run_db = DataStore("workflow_run", data_model=WorkflowRun, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    workflow_scheduler = WorkflowScheduler(workflow_db, workflow_run_db)
    workflow_scheduler.schedule("e7b01fd3-dbbf-4b0b-8cd0-24702d68e6d0")



