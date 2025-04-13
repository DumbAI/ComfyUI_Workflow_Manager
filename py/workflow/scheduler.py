# scheduler module poll job queue and launch workflows
import os
import boto3
from datetime import datetime
from typing import Dict
import io
import time
import uuid
import json
import shutil
from boto3.dynamodb.conditions import Key, Attr

from .dao import Workspace, reconstruct_workflow, reconstruct_inventory, get_workflow_manifest
from .controller import run_workflow 
from loguru import logger

from .database import *

from job_queue import JobQueue, DynamoDBJobQueue, SingleThreadJobScheduler, EchoWorkflow, Workflow, JobRequest, JobResponse, File

def write_input_file(input_file_path, file: File):
    # make directory if not exist
    os.makedirs(os.path.dirname(input_file_path), exist_ok=True)
    
    # write input buffer to file on disk
    with open(input_file_path, 'wb') as f:
        f.write(file.content.read())
    

class ComfyWorkflow(Workflow):
    def __call__(self, request: JobRequest) -> JobResponse:
        logger.info(f'Processing job {request}')
        
        # FIXME: workflow should be already installed in the workspace
        base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
        workspace = Workspace(base_path=base_path)
        # for each job, launch the workflow process
        # FIXME: different poller should dispatch to different workflow
        workflow_id = request.Params.get('workflow_id', 4)
        workflow_record_to_run = get_workflow_by_id(workflow_id)
        logger.info(workflow_record_to_run)

        temp_input_file_dir = f'/{uuid.uuid4()}'
        input_files = []
        for input_file in request.InputFiles:
            file_name = input_file.Name
            logger.info(f'Processing input file {file_name}')
            if input_file.content is None:
                raise Exception('Input file content is None')
            
            download_file_path = f'{workspace.user_space_path}/{temp_input_file_dir}/{file_name}'
            # make directory if not exist
            write_input_file(download_file_path, input_file)
            input_files.append(download_file_path)
        
        # Resolve input override
        input_override = request.Params.get('input_override', {})
        workflow_input_override_json_file = f'{workflow_record_to_run.workflow_dir}/input_override.json'
        override_template = {}
        with open(workflow_input_override_json_file, 'r') as f:
            workflow_input_override_json = json.load(f)
            
            # override value using parameters from request
            override_value = workflow_input_override_json.get('override_value', {})
            override_value.update(input_override)
            
            # interpolate override value into override template
            override_template=workflow_input_override_json.get('override_template', {})
            # recursively update the input value in override template
            def update_input_value(override_value, override_template):
                for k, v in override_template.items():
                    if isinstance(v, dict):
                        update_input_value(override_value, v)
                    else:
                        if v in override_value:
                            override_template[k] = override_value[v]
            update_input_value(
                override_value, 
                override_template
            )

        # Launch workflow
        logger.info(f'Launching workflow {workflow_record_to_run}')
        workflow_run = run_workflow(
            workspace, 
            workflow_record_to_run,
            input_files=input_files,
            input_override=override_template
        )
        logger.info(workflow_run)

        # Recursively list all files from the output directory
        output_files = []
        for root, dirs, files in os.walk(workflow_run.output_dir):
            for file in files:
                logger.info(f'Processing file {root}, {dirs}, {file}')
                with open(f'{root}/{file}', 'rb') as f:
                    content = f.read()
                    out_file = File(Name=file)
                    out_file.content = io.BytesIO(content)
                    output_files.append(out_file)
        
        return JobResponse(OutputFiles=output_files)
        

if __name__ == '__main__':
    job_queue = DynamoDBJobQueue(
        table_name='xiaoapp-job-queue', 
        secondary_index_name='QueueIndex', 
        bucket_name='xiaoapp-job-data'
    )

    scheduler = SingleThreadJobScheduler(job_queue)
    scheduler.register_workflow('echo', ComfyWorkflow())
    scheduler.run()

