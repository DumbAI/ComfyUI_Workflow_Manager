""" Schedule the workflow execution
1) create or allocate a worker
2) assign a workflow to the worker
3) monitor the workflow execution, update run status
"""
import uuid
import os
import sys
import time
import json
from datetime import datetime
import subprocess
import random
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from workflow.in_mem_store import DataStore
from workflow.db import Workflow, WorkflowRun, Dir
from workflow.utils import logger

import requests

# Global data stores
workflow_db = DataStore("workflow", data_model=Workflow, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
workflow_run_db = DataStore("workflow_run", data_model=WorkflowRun, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')

def force_create_symlink(source, link_name):
    """ Create a symlink, remove existing file or symlink if exists"""
    if os.path.isfile(source):
        if os.path.exists(link_name) or os.path.islink(link_name):
            os.remove(link_name)
        os.symlink(source, link_name)

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


class ComfyService:

    def __init__(self, host: str, port: str):
        self.host = host
        self.port = port

    def is_server_ready(self) -> bool:
        try:
            url = f"http://{self.host}:{self.port}/queue"
            # check server status is 200
            response = requests.get(url)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            return False
    




class ComfyUIProcessRunner(Runner):
    """ Run a ComfyUI workflow in a subprocess
    Reference: https://github.com/Comfy-Org/comfy-cli/blob/main/comfy_cli/command/launch.py
    TODO: manage server lifecycle using a state machine 
    """

    PROC_SHUTDOWN_TIMEOUT_SEC = 5

    class PromptResponse(BaseModel):
        prompt_id: str
        number: int
        node_errors: Optional[Dict] = None

    def __init__(self, workflow: Workflow, workflow_run: WorkflowRun):
        self.workflow = workflow
        self.workflow_run = workflow_run
        # run ComfyUI main process
        self.host = '127.0.0.1'
        self.port = str(random.randint(8189, 49151)) # random port
        self.comfyui_service = ComfyService(self.host, self.port)

    def _launch_comfyui(self, extra):
        reboot_path = None

        session_path = self.workflow_run.output_dir.dir_path if self.workflow_run.output_dir is not None else f'/tmp/comfyui-workflow/{self.workflow_run.id}'
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

        workspace_dir = self.workflow_run.workspace.dir_path
        output_dir = self.workflow_run.output_dir.dir_path

        # TODO: setup comfyui workspace (pull from git if needed)

        # TODO: create session dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_dir = f'{self.workflow_run.output_dir.dir_path}/output'
        # create output dir if not exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # FIXME: create a process cache, allow reused of processes. 
        # FIXME: manage server lifecycle using a state machine

        # create symlink for all files in workflow input dir
        # merge workflow input files and input override files
        comfyui_input_dir = f'{self.workflow_run.input_dir.dir_path}/merge'
        os.makedirs(comfyui_input_dir, exist_ok=True)
        
        input_files = os.listdir(self.workflow.input_dir.dir_path)
        for input_file in input_files:
            input_file_path = os.path.join(self.workflow.input_dir.dir_path, input_file)
            force_create_symlink(input_file_path, os.path.join(comfyui_input_dir, input_file))
        # files in workflow run input dir should override files from workflow input dir
        input_files = os.listdir(self.workflow_run.input_dir.dir_path)
        for input_file in input_files:
            input_file_path = os.path.join(self.workflow_run.input_dir.dir_path, input_file)
            force_create_symlink(input_file_path, os.path.join(comfyui_input_dir, input_file))
            

        
        # ComfyUI args
        # extra model paths config
        # 1) model path
        # 2) extra custom model path
        # 3) workflow/run input path
        # 4) run output path
        args = [
            '--listen', self.host,
            '--port', self.port,
            '--output-directory', f'{self.workflow_run.output_dir.dir_path}/output',
            '--input-directory', comfyui_input_dir,
        ]
        
        os.chdir(workspace_dir)
        self.process = self._launch_comfyui(args)
        # self.proc = subprocess.Popen(command, capture_output=True, capture_error=True)
        # subprocess.run(command, capture_output=True, capture_error=True)

        # check server status
        # url = f"http://{self.host}:{self.port}/status"
        while not self.comfyui_service.is_server_ready():
            logger.info(f"Waiting for ComfyUI server to be ready: {self.host}:{self.port}")
            time.sleep(5)


    def run(self):
        workflow_config = None
        workflow_api_config_file = f'{self.workflow.metadata_dir.dir_path}/workflow_api.json'
        with open(workflow_api_config_file, 'r') as f:
            workflow_config = json.load(f)

        # override input
        input_override_data = None
        if os.path.exists(f'{self.workflow_run.input_dir.dir_path}'):
            # override input value and input files
            with open(f'{self.workflow_run.input_dir.dir_path}/input_override.json', 'r') as f:
                input_override_data = json.load(f)
                for k, v in input_override_data.items():
                    inputs = v.get('inputs', None)
                    if inputs is not None:
                        # TODO: only update fields that are in the input_override
                        # keep the rest of the input values unchanged
                        workflow_config[k]['inputs'].update(inputs)
            


        if workflow_config is None:
            logger.error(f"Error loading workflow config from {workflow_api_config_file}")
            return
        
        url = f"http://{self.host}:{self.port}/prompt"
        response = requests.post(url, json={"prompt": workflow_config})
        prompt_response = ComfyUIProcessRunner.PromptResponse(**response.json())
        if prompt_response.node_errors and len(prompt_response.node_errors.keys()) > 0:
            logger.error(f"Error running workflow: {prompt_response.node_errors}")
            return
        
        get_response = requests.get(url)
        get_response_json = get_response.json()
        logger.info(get_response_json)
        prompt_id = prompt_response.prompt_id
        logger.info(f"Prompt ID: {prompt_id}")
        while True:
            logger.info(f"Checking workflow status: {prompt_id}")
            get_history_response = requests.get(f'http://{self.host}:{self.port}/history/{prompt_id}')
            get_history_response_json = get_history_response.json()
            prompt_status = get_history_response_json.get(f'{prompt_id}', None)

            if prompt_status is None:
                logger.info(f"Prompt {prompt_id} Workflow not completed yet, no status returned")
                time.sleep(5)
                continue
            
            status = prompt_status.get('status', None)
            if status is None or not status.get('completed', False):
                # pull status again
                logger.info(f"Prompt {prompt_id} Workflow not completed yet: {status}")
                time.sleep(5)
                continue
            
            if status.get('status_str', None) == 'success':
                logger.info(f"Workflow completed successfully: {status}")
            else: 
                # Better error handling
                logger.error(f"[Error]: running workflow: {status}")

            self.workflow_run.status = status.get('status_str', None)
            output_dir = self.workflow_run.output_dir.dir_path
            prompt_history_file = os.path.join(output_dir, f'prompt_history_{prompt_id}.json')
            # write prompt history to file
            with open(prompt_history_file, 'w') as f:
                json.dump(get_history_response_json, f)

            workflow_run_db.put(self.workflow_run) 
            return


    def teardown(self):
        try:
            self.process.terminate()
            self.process.wait(timeout=ComfyUIProcessRunner.PROC_SHUTDOWN_TIMEOUT_SEC) # wait for 5 seconds
            returncode = self.process.poll()
            logger.info(f"Process terminated with return code: {returncode}")
            if returncode is None:
                # process has not exit yet, force kill it
                self.process.kill()
        except Exception as e:
            logger.error(f"Error terminating process: {e}. Force killing the process.")
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
        logger.info(f"Workflow: {workflow}")
        logger.info(f"Workflow Run: {workflow_run}")

        runner = ComfyUIProcessRunner(workflow, workflow_run)
        self.run_registry[workflow_run.id] = runner
        logger.info(f"Starting workflow run: {workflow_run.id}")
        runner.setup()
        # time.sleep(60)
        runner.run()
        logger.info(f"Terminating workflow run: {workflow_run.id}")
        runner.teardown()



if __name__ == "__main__":
    # workflow_db = DataStore("workflow", data_model=Workflow, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    # workflow_run_db = DataStore("workflow_run", data_model=WorkflowRun, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    workflow_scheduler = WorkflowScheduler(workflow_db, workflow_run_db)
    workflow_scheduler.schedule("e7b01fd3-dbbf-4b0b-8cd0-24702d68e6d0")




