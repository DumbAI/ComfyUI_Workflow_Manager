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
import atexit
import signal

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from workflow.in_mem_store import DataStore
from workflow.db import Workflow, WorkflowRun, Dir
from workflow.utils import logger

import requests
from queue import Queue

# a global registry of all subprocesses
subprocesses = Queue()

def cleanup():
    for i in range(subprocesses.qsize()):
        process = subprocesses.get()
        if process.poll() is None:  # Check if the process is still running
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

def handle_signal(signum, frame):
    cleanup()
    sys.exit(0)

# Register the cleanup function to be called on exit
atexit.register(cleanup)

# Register signal handlers
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)



class Runner(ABC):
    """ Abstract class for running a workflow """

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


    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.run_id = str(uuid.uuid4())
        
        # workspace directories
        self.work_dir = self.workflow.workflow_dir
        self.input_dir = self.workflow.input_dir
        self.output_dir = self.workflow.output_dir
        self.temp_dir = self.workflow.temp_dir

        # run ComfyUI main process
        self.host = '0.0.0.0'
        self.port = str(random.randint(8189, 49151)) # random port
        self.comfyui_service = ComfyService(self.host, self.port)


    def _launch_comfyui(self, extra_args):
        """ Launch ComfyUI server in a subprocess, using conda venv and python module
        """

        # venv
        conda_venv_path = self.workflow.python_venv.conda_env_path

        python_env = {
            "PYTHONENCODING":"utf-8", # is this required?
            'PYTHONPATH': self.workflow.main_module_dir
        }

        # To minimize the possibility of leaving residue in the tmp directory, use files instead of directories.
        # reboot_path = None
        # self.reboot_path = os.path.join(session_path, ".reboot")

        extra_args = extra_args if extra_args is not None else []
        
        command = f'conda run -p {conda_venv_path}'
        for k, v in python_env.items():
            command += f' {k}={v}'
        command += f' python -m main ' + ' '.join(extra_args)

        process = None
        
        log_file = os.path.join(self.output_dir, "workflow.log")

        try:
            with open(log_file, "w") as f:
                if sys.platform == "win32":
                    process = subprocess.Popen(
                        command.split(),
                        stdout=f,
                        stderr=f,
                        text=True,
                        env=os.environ,
                        encoding="utf-8",
                        shell=True,  # win32 only
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # win32 only
                    )
                else:
                    print(f"Running: {command}")
                    process = subprocess.Popen(
                        command.split(),
                        text=True,
                        env=os.environ, # so that conda env is available
                        encoding="utf-8",
                        stdout=f,
                        stderr=f,
                    )
                subprocesses.put(process)
                return process
        except KeyboardInterrupt:
            if process is not None:
                os._exit(1)


    def setup(self):
        """ Setup the ComfyUI server and wait for it to be ready """

        # FIXME: create a process cache, allow reused of processes. 
        # FIXME: manage server lifecycle using a state machine

        # ComfyUI args
        # extra model paths config
        # 1) model path
        # 2) extra custom model path
        # 3) workflow/run input path
        # 4) run output path
        args = [
            '--listen', self.host,
            '--port', self.port,
            '--input-directory', self.input_dir,
            '--output-directory', self.output_dir,
            '--temp-directory', self.temp_dir,
            '--extra-model-paths-config', f'{self.work_dir}/extra_model_paths.yaml',
            '--verbose',
        ]
        
        # os.chdir(self.work_dir)
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
        workflow_api_config_file = f'{self.work_dir}/workflow_api.json'
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

            # workflow_run_db.put(self.workflow_run) 
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

            # terminate the sub python process launched by conda
            import psutil
            import signal
            import sys

            def get_conda_python_processes():
                conda_python_path = self.workflow.python_venv.python_path
                conda_python_processes = []

                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        if proc.info['exe'] is not None and os.path.samefile(proc.info['exe'], conda_python_path):
                            conda_python_processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

                return conda_python_processes

            for p in get_conda_python_processes():
                pid = p['pid']
                if pid == os.getpid(): continue # dont kill current process
                logger.info(f"Terminating python process: {pid}")
                # FIXME: this could kill all python process launched by the same conda env. 
                # TODO: workflow manage need to manage its own conda env as well.
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Error terminating process: {e}. Force killing the process.")
                    # os.kill(pid, signal.SIGKILL)

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


if __name__ == "__main__":
    # Global data stores
    # workflow_db = DataStore("workflow", data_model=Workflow, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    # workflow_run_db = DataStore("workflow_run", data_model=WorkflowRun, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    # workflow_db = DataStore("workflow", data_model=Workflow, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    # workflow_run_db = DataStore("workflow_run", data_model=WorkflowRun, store_path='/home/ruoyu.huang/workspace/xiaoapp/ComfyUI_Workflow_Manager/.db')
    # workflow_scheduler = WorkflowScheduler(workflow_db, workflow_run_db)
    # workflow_scheduler.schedule("e7b01fd3-dbbf-4b0b-8cd0-24702d68e6d0")

    pass