from pydantic import BaseModel, Field
import uuid
import json
import os

from typing import Optional, List, Tuple, Dict

from sqlmodel import Field, SQLModel, create_engine

from workflow.in_mem_store import DataStore
from workflow.utils import force_create_symlink


class Dir(BaseModel):
    """  encapsulates a directory
    """
    dir_path: str



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
    python_path: Optional[str] = None 
    env_vars: Optional[EnvVars] = None


class Dependency(BaseModel):
    """  encapsulates a dependency
    """

class ModelDependency(BaseModel):
    """  encapsulates a model
    FIXME: only support remote public model for now
    TODO: Use Git LFS format:
        ```
        version https://git-lfs.github.com/spec/v1
        oid sha256:9fae2e50cb431bfcbe05822b59ec2228df545ef27f711dea8949e9f4ed9f7cdc
        size 2513342408
        ```
    """
    name: str # should be same as the model file name
    file_name: str # model file name including extension
    rel_file_path: str # relative file path to the model_base_path, this is handle used to reference the model
    category: str | None # model category
    url: str | None

class CodeDependency(BaseModel):
    """  encapsulates a remote code repo
    """
    name: str # should be same as the repo name
    github_url: str
    commit_sha: str
    tag: Optional[str] = None

class FileDependency(BaseModel):
    """  encapsulates a file
    """
    file_path: str


class Inventory(BaseModel):
    """ Physical file system inventory that contains all the dependencies
    Inventory enforce opinionated folder structure for each type of dependency
    """
    base_path: str
    modules: Dict[str, CodeDependency] # {module name -> module dependency}
    models: Dict[str, Tuple[str, ModelDependency]] # {model category -> (model name, model dependency)}

    def check_module_exist(self, module_name) -> None:
        if self.modules.get(module_name, None) is None:
            raise ValueError(f"Module {module_name} not found in inventory")

    def check_model_exist(self, model_rel_path):
        if self.models.get(model_rel_path, None) is None:
            raise ValueError(f"Model {model_rel_path} not found in inventory")
    

class ComfyUIWorkspaceConfig(BaseModel):
    # folder structure
    custom_node_dir: str = Field(default = 'custom_nodes', description='custom nodes folder')
    custom_model_dir: str = Field(default = 'custom_models', description='custom models folder')
    input_dir: str = Field(default = 'input', description='inputs folder')
    output_dir: str = Field(default = 'output', description='outputs folder')
    temp_dir: str = Field(default = 'temp', description='temp folder')

    # ComfyUI extra_model_paths.yaml
    # checkpoints: str | None = Field(default='models/checkpoints/')
    # clip: str | None = Field(default = 'models/clip/')
    # clip_vision: str | None = Field(default = 'models/clip_vision/')
    # configs: str | None = Field(default = 'models/configs/')
    # controlnet: str | None = Field(default = 'models/controlnet/')
    # embeddings: str | None = Field(default = 'models/embeddings/')
    # loras: str | None = Field(default = 'models/loras/')
    # upscale_models: str | None = Field(default = 'models/upscale_models/')
    # vae: str | None = Field(default = 'models/vae/')

    

class ComfyUIDependencyConfig(BaseModel):
    # depdenencies
    base_code: CodeDependency = Field(description='base code for comfyui')
    custom_nodes: List[CodeDependency] = Field(default = [], description='custom nodes')
    custom_models: List[ModelDependency] = Field(default = [], description='custom models')


def _validate_dir(dir_path, create=False):
    assert dir_path is not None, f'Directory path is None'
    
    if create:
        os.makedirs(dir_path, exist_ok=True)

    assert os.path.exists(dir_path) and os.path.isdir(dir_path), f'Failed to create directory {dir_path}'


def _create_symlink(src, dst):
    tmp_link = f'{dst}.tmp'
    os.symlink(src=src, dst=tmp_link, target_is_directory=True)
    os.rename(tmp_link, dst)

class Workflow(BaseModel):
    """ Apps can be installed and expands into a workflow
    Apps:
        - input
        - workflow.json, workflow_api.json
        - dependency.json # list of custom nodes and models

    Workflow: (After App is installed)
        - manifest.json # workflow metadata
        - output
        - temp
        - custom_nodes # symlink to modules in inventory
        - custom_models # symlink to models in inventory
        - ComfyUI # symlink to ComfyUI main repo
    """

    id: str | None = Field(default=None, primary_key=True)
    name: str
    category: str = Field(default='comfyui', description='workspace category')
    description: str = Field(default='comfyui workflow', description='workflow description')
    workflow_dir: str = Field(description='workflow base directory')

    # workspace structure
    workspace_config: ComfyUIWorkspaceConfig

    # dependencies
    python_venv: PythonCondaEnv
    dependency_config: ComfyUIDependencyConfig

    @property
    def main_module_dir(self):
        return f'{self.workflow_dir}/ComfyUI'

    @property
    def input_dir(self):
        return f'{self.workflow_dir}/{self.workspace_config.input_dir}'
    
    @property
    def output_dir(self):
        return f'{self.workflow_dir}/{self.workspace_config.output_dir}'
    
    @property
    def temp_dir(self):
        return f'{self.workflow_dir}/{self.workspace_config.temp_dir}'
    
    @property
    def custom_node_dir(self):
        return f'{self.workflow_dir}/{self.workspace_config.custom_node_dir}'
    
    @property
    def custom_model_dir(self):
        return f'{self.workflow_dir}/{self.workspace_config.custom_model_dir}'

    def comfyui_path(self):
        return self.dependency_config.base_code

    def prepare_workspace(self, inventory: Inventory):
        # TODO: validate workspace
        _validate_dir(self.workflow_dir)
        # _validate_dir(self.workspace_config.custom_node_dir, create=True)
        # _validate_dir(self.workspace_config.custom_model_dir, create=True)
        _validate_dir(f'{self.workflow_dir}/{self.workspace_config.input_dir}', create=True)
        _validate_dir(f'{self.workflow_dir}/{self.workspace_config.output_dir}', create=True)
        _validate_dir(f'{self.workflow_dir}/{self.workspace_config.temp_dir}', create=True)

        # Customer Modules
        def _check_code_module(existing_code_module, required_code_module):
            # compare the two code modules are the same
            assert existing_code_module.name == required_code_module.name, 'Name does not match'
            assert existing_code_module.github_url == required_code_module.github_url, 'Github url does not match'
            assert existing_code_module.commit_sha == required_code_module.commit_sha, 'Commit sha does not match'
            return True

        assert _check_code_module(
            existing_code_module=inventory.modules['ComfyUI'],
            required_code_module=self.dependency_config.base_code
        ), 'Base code module does not match'
        # link to ComfyUI
        _create_symlink(
                f'{inventory.base_path}/modules/ComfyUI', 
                f'{self.workflow_dir}/ComfyUI')

        for custom_node in self.dependency_config.custom_nodes:
            inventory.check_module_exist(custom_node.name)
            assert _check_code_module(
                existing_code_module=inventory.modules[custom_node.name],
                required_code_module=custom_node
            ), f'Custom node {custom_node.name} does not match'
            
        # Create symbolic link to custom modules
        # FIXME: for simplicity, it suffices to create a symbolic link to the root modules directory
        # TODO: create virtual inventory if necessary in the future
        _create_symlink(
            f'{inventory.base_path}/modules', 
            f'{self.workflow_dir}/{self.workspace_config.custom_node_dir}')


        # Custom models
        def _check_model(existing_model, required_model):
            # compare the two models are the same
            assert existing_model.name == required_model.name, 'Name does not match'
            assert existing_model.file_name == required_model.file_name, 'File name does not match'
            assert existing_model.rel_file_path == required_model.rel_file_path, 'Rel file path does not match'
            assert existing_model.category == required_model.category, 'Category does not match'
            return True

        for custom_model in self.dependency_config.custom_models:
            inventory.check_model_exist(custom_model.rel_file_path)
            _, model_dependency = inventory.models[custom_model.rel_file_path]
            assert _check_model(model_dependency, custom_model), f'Custom model {custom_model.rel_file_path} does not match'

        # Create symbolic link to custom models
        # FIXME: for simplicity, it suffices to create a symbolic link to the root model directory
        custom_model_dir = f'{self.workflow_dir}/{self.workspace_config.custom_model_dir}'
        _create_symlink(f'{inventory.base_path}/models', custom_model_dir)

        with open(f'{self.workflow_dir}/manifest.json', 'w') as f:
            f.write(self.model_dump_json())

        import yaml
        extra_model_paths = {
            'comfyui': {
                'base_path': f'{self.workflow_dir}/ComfyUI',
                'custom_nodes': f'{self.custom_node_dir}',
                'checkpoints': f'{self.custom_model_dir}/checkpoints/',
                'clip': f'{self.custom_model_dir}/clip/',
                'clip_vision': f'{self.custom_model_dir}/clip_vision/',
                'configs': f'{self.custom_model_dir}/configs/',
                'controlnet': f'{self.custom_model_dir}/controlnet/',
                'embeddings': f'{self.custom_model_dir}/embeddings/',
                'loras': f'{self.custom_model_dir}/loras/',
                'upscale_models': f'{self.custom_model_dir}/upscale_models/',
                'vae': f'{self.custom_model_dir}/vae/'
            }
        } 
        with open(f'{self.workflow_dir}/extra_model_paths.yaml', 'w') as f:
            yaml_data = yaml.dump(extra_model_paths, default_flow_style=False)
            f.write(yaml_data)
        
    def launch(self):
        pass



class WorkflowRun(BaseModel):
    id: Optional[str] = Field(default=None, primary_key=True)
    workflow: Optional[Workflow] = Field(description='workflow associated with this run') 

    # Runtime directories override
    work_dir: Optional[Dir] = None # ComfyUI workspace
    input_dir: Optional[Dir] = None # deprecated
    output_dir: Optional[Dir] = None

    # Runtime info
    status: Optional[str] = None
    start_time: str | None = None
    end_time: str | None = None

    def prepare_workspace(self, workflow: Workflow):

        # merge in input files from workflow input dir
        input_files = os.listdir(self.workflow.input_dir)
        for input_file in input_files:
            input_file_path = os.path.join(self.workflow.input_dir, input_file)
            target = os.path.join(self.input_dir, input_file)
            
            # files in workflow run input dir should override files from workflow input dir
            if not os.path.exists(target):
                force_create_symlink(input_file_path, os.path.join(self.input_dir, input_file))

        # TODO: create output dir
            

def run_workflow():
    workflow_1 = Workflow(
        id=str(uuid.uuid4()),
        name="workflow_1", 
        description="workflow 1", 
        env=PythonCondaEnv(conda_env_path="/home/ruoyu.huang/miniconda3/envs/xiaoapp"),
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



def reconstruct_inventory(base_path):
    # build inventory

    import os
    import subprocess
    import json
    # list all subfolders in the base_path
    

    def reconstruct_module(module_path):
        # git remote get-url --push origin
        # git branch --show-current
        # git rev-parse HEAD
        remote_url = subprocess.run(["git", "remote", "get-url", "--push", "origin"], cwd=module_path, capture_output=True, text=True).stdout.strip()
        # branch = subprocess.run(["git", "branch", "--show-current"], cwd=module_path, capture_output=True, text=True).stdout.strip()
        commit_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=module_path, capture_output=True, text=True).stdout.strip()
        tags = subprocess.run(["git", "tag", "--points-at", "HEAD"], cwd=module_path, capture_output=True, text=True).stdout.strip()

        return CodeDependency(
            name=os.path.basename(module_path), 
            github_url=remote_url, 
            commit_sha=commit_sha,
            tags=tags)

    modules = {}
    
    modules_base_path = f"{base_path}/modules"
    for sub_dir in os.listdir(modules_base_path):
        if os.path.isdir(os.path.join(modules_base_path, sub_dir)):
            if sub_dir == '__pycache__':
                continue

            modules[sub_dir] = reconstruct_module(os.path.join(modules_base_path, sub_dir))

    models = {}
    models_base_path = f'{base_path}/models'
    for root, dirs, files in os.walk(models_base_path):
        for model_file in files:
            model_path = os.path.join(root, model_file)
            model_size = os.path.getsize(model_path)
            if model_size == 0:
                # skip empty file
                continue
            filename = os.path.basename(model_file)
            rel_path = os.path.relpath(model_path, models_base_path)
            category = rel_path.split('/')[0] 
            models[rel_path] = (category, ModelDependency(
                name=filename, 
                file_name=filename, 
                rel_file_path=rel_path,
                category=category, 
                url=f'file:{model_path}'))


    inventory = Inventory(
        base_path=base_path, 
        modules=modules,
        models=models)
    breakpoint()
    with open(f'{base_path}/inventory.json', 'w') as f:
        f.write(inventory.model_dump_json())

    return inventory

# Main ComfyUI repo
# main_code_repo=CodeRepo(github_url="git@github.com:comfyanonymous/ComfyUI.git", commit_sha='4ca9b9cc29fefaa899cba67d61a8252ae9f16c0d', tag='v0.0.1')

def reconstruct_workflow(base_path):
    
    # ComfyUI base code v0.0.7
    code = CodeDependency(
        **{
            "name": "ComfyUI",
            "github_url": "git@github.com:comfyanonymous/ComfyUI.git",
            "commit_sha": "b8ffb2937f9daeaead6e9225f8f5d1dde6afc577",
        })
    
    models = []
    modules = []
    with open(f'{base_path}/dependency.json', 'r') as f:
        dependency = json.load(f)
        for m in dependency['models']:
            models.append(ModelDependency(**m))
        for m in dependency['modules']:
            modules.append(CodeDependency(**m))
    
    dependency_config = ComfyUIDependencyConfig(base_code=code, 
                            custom_nodes=modules, 
                            custom_models=models)

    workflow = Workflow(
        id=str(uuid.uuid4()),
        name="all_in_one_controlnet", 
        category="comfyui",
        description="All in one control net", 
        workflow_dir=base_path,
        workspace_config=ComfyUIWorkspaceConfig(),
        python_venv=PythonCondaEnv(
            conda_env_path="/home/ruoyu.huang/miniconda3/envs/xiaoapp",
            python_path='/home/ruoyu.huang/miniconda3/envs/xiaoapp/bin/python'),
        dependency_config=dependency_config
    )
    
    return workflow


def get_workflow_manifest(workflow_dir: str):
    manifest_path = f'{workflow_dir}/manifest.json'
    with open(manifest_path, 'r') as f:
        workflow_to_run = Workflow.model_validate(json.load(f))
        return workflow_to_run

if __name__ == "__main__":
    base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace"
    inventory = reconstruct_inventory(base_path)
    workflow_base_path = "/home/ruoyu.huang/workspace/xiaoapp/comfyui_workspace/workflows/all_in_one_controlnet"
    workflow = reconstruct_workflow(workflow_base_path)
    print(workflow)
    workflow.prepare_workspace(inventory)
    






