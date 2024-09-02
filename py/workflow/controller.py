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
from typing import Dict, List, Optional, Tuple, Callable
from pydantic import BaseModel, Field

from .dao import Workflow, Workspace, Dir
from workflow.database import WorkflowRunRecord
from workflow.utils import logger, force_create_symlink

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
    

class ComfyUIRunner(Runner):
    """ Run a ComfyUI workflow in a subprocess
    Reference: https://github.com/Comfy-Org/comfy-cli/blob/main/comfy_cli/command/launch.py
    TODO: manage server lifecycle using a state machine 
    TODO: allocate GPU resources, shared cross multiple workflow runs
    """

    PROC_SHUTDOWN_TIMEOUT_SEC = 5

    class PromptResponse(BaseModel):
        prompt_id: str
        number: int
        node_errors: Optional[Dict] = None


    def __init__(self, workspace: Workspace, workflow: Workflow, workflow_run: WorkflowRunRecord,
                 callback: Optional[Callable[[WorkflowRunRecord], None]] = None):
        self.workspace = workspace
        self.workflow = workflow
        self.callback = callback # callback for status update
        
        self.run_id = str(uuid.uuid4())
        
        # run time directories
        workflow_run.runtime_dir = os.path.join(self.workspace.workflow_run_path, self.run_id) 
        self.workflow_run = workflow_run
        self.work_dir = self.workflow_run.runtime_dir
        self.input_dir = self.workflow_run.input_dir
        self.output_dir = self.workflow_run.output_dir
        self.temp_dir = self.workflow_run.temp_dir


        # run ComfyUI main process
        self.host = '0.0.0.0'
        self.port = str(random.randint(8189, 49151)) # random port
        self.comfyui_service = ComfyService(self.host, self.port)


        # TODO: update workflow_run in database
        self._update_status("pending")


    def _update_status(self, status: str):
        self.workflow_run.status = status
        self.workflow_run.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.callback(self.workflow_run)


    def _launch_comfyui(self, extra_args):
        """ Launch ComfyUI server in a subprocess, using conda venv and python module
        """

        # venv
        python_path = self.workflow.python_venv.virtualenv_python_path

        # TODO: pass CUDA_VISIBLE_DEVICES from input
        python_env = {
            "PYTHONENCODING":"utf-8", # is this required?
            'PYTHONPATH': self.workflow.main_module_dir, # points to ComfyUI, so that main module can be found
            'CUDA_VISIBLE_DEVICES': '0'
        }

        # To minimize the possibility of leaving residue in the tmp directory, use files instead of directories.
        # reboot_path = None
        # self.reboot_path = os.path.join(session_path, ".reboot")

        extra_args = extra_args if extra_args is not None else []
        
        
        command = f' {python_path} -m main ' + ' '.join(extra_args)
        process = None

        try:
            with open(self.workflow_run.log_file, "w") as f:
                if sys.platform == "win32":
                    process = subprocess.Popen(
                        command.split(),
                        stdout=f,
                        stderr=f,
                        text=True,
                        env=python_env,
                        encoding="utf-8",
                        shell=True,  # win32 only
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # win32 only
                    )
                else:
                    print(f"Running: {command}")
                    process = subprocess.Popen(
                        command.split(),
                        text=True,
                        env=python_env,
                        encoding="utf-8",
                        stdout=f,
                        stderr=f,
                    )
                subprocesses.put(process)
                return process
        except KeyboardInterrupt:
            if process is not None:
                os._exit(1)

    # prepare workflow run dir
    def _prepare_runtime_dir(self):
        # create input and output dir if not exists
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

        # merge in input files from workflow input dir
        input_files = os.listdir(self.workflow.input_dir)
        for input_file in input_files:
            input_file_path = os.path.join(self.workflow.input_dir, input_file)
            target = os.path.join(self.input_dir, input_file)
            
            # files in workflow run input dir should override files from workflow input dir
            if not os.path.exists(target):
                force_create_symlink(input_file_path, os.path.join(self.input_dir, input_file))


    def setup(self):
        """ Setup runtime directory and the ComfyUI server and wait for it to be ready """
        self._prepare_runtime_dir()

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
            '--extra-model-paths-config', self.workflow.extra_model_paths,
            '--verbose',
        ]
        
        # os.chdir(self.work_dir)
        self.process = self._launch_comfyui(args)

        # check server status
        # url = f"http://{self.host}:{self.port}/status"
        while not self.comfyui_service.is_server_ready():
            logger.info(f"Waiting for ComfyUI server to be ready: {self.host}:{self.port}")
            time.sleep(5)

        self._update_status("ready")


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
        prompt_response = ComfyUIRunner.PromptResponse(**response.json())
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
            self._update_status("running")


    def teardown(self):
        try:
            self.process.terminate()
            self.process.wait(timeout=ComfyUIRunner.PROC_SHUTDOWN_TIMEOUT_SEC) # wait for 5 seconds
            returncode = self.process.poll()
            logger.info(f"Process terminated with return code: {returncode}")
            if returncode is None:
                # process has not exit yet, force kill it
                self.process.kill()
        except Exception as e:
            logger.error(f"Error terminating process: {e}. Force killing the process.")
            self.process.kill()
        finally:
            self._update_status("terminated")