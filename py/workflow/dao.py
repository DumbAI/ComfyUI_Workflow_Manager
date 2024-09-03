from pydantic import BaseModel, Field, computed_field
import uuid
import json
import os
import subprocess
import shutil

from typing import Optional, List, Tuple, Dict

from sqlmodel import Field

from .utils import run_command



class Dir(BaseModel):
    """  encapsulates a directory
    """
    dir_path: str

class EnvVars(BaseModel):
    """  encapsulates an env var
    """
    env_var_list: List[Tuple[str, str]] 


class RuntimeEnv(BaseModel):
    venv_path: str
    env_vars: Optional[EnvVars] = None

    @computed_field
    def virtualenv_python_path(self) -> str:
        # Reference: https://github.com/ray-project/ray/blob/80e832c6c68885f4b3f01a5f807e381bf99eb8dc/python/ray/_private/runtime_env/pip.py#L51
        _WIN32 = os.name == "nt"
        if _WIN32:
            return os.path.join(self.venv_path, "Scripts", "python.exe")
        else:
            return os.path.join(self.venv_path, "bin", "python")

    @computed_field
    def virtualenv_activate_command(self) -> List[str]:
        _WIN32 = os.name == "nt"
        if _WIN32:
            cmd = [os.path.join(self.venv_path, "Scripts", "activate.bat")]
        else:
            cmd = ["source", os.path.join(self.venv_path, "bin/activate")]
        return cmd + ["1>&2", "&&"]



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

class Workspace(BaseModel):
    """ Physical file system that contains all files and dependencies
    Workspace enforce opinionated folder structure for each type of dependency
    """
    base_path: str

    @computed_field
    def base_code_path(self) -> str:
        return f'{self.base_path}/ComfyUI'
    
    @computed_field
    def module_path(self) -> str:
        return f'{self.base_path}/modules'
    
    @computed_field
    def model_path(self) -> str:
        return f'{self.base_path}/models'
    
    @computed_field
    def workflow_path(self) -> str:
        return f'{self.base_path}/workflows'
    
    @computed_field
    def workflow_run_path(self) -> str:
        return f'{self.base_path}/workflow_runs'
    
    @computed_field
    def database_file_path(self) -> str:
        return f'{self.base_path}/workflow.db'

    @computed_field
    def user_space_path(self) -> str:
        return f'{self.base_path}/user_space'


class Inventory(BaseModel):
    """ Abstarct inventory over physical workspace that contains all the dependencies
    One physical workspace can have multiple inventories
    """
    workspace: Workspace
    base_code: CodeDependency
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
    dir = os.path.dirname(dst)
    if not os.path.exists(dst):
        os.makedirs(dir, exist_ok=True)

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

    # dependencies
    python_venv: RuntimeEnv
    dependency_config: ComfyUIDependencyConfig

    @property
    def main_module_dir(self):
        return f'{self.workflow_dir}/ComfyUI'

    @property
    def input_dir(self):
        return f'{self.workflow_dir}/input'
    
    @property
    def output_dir(self):
        return f'{self.workflow_dir}/output'
    
    @property
    def temp_dir(self):
        return f'{self.workflow_dir}/temp'
    
    @property
    def custom_node_dir(self):
        return f'{self.workflow_dir}/ComfyUI/custom_nodes'
    
    @property
    def custom_model_dir(self):
        return f'{self.workflow_dir}/ComfyUI/models'
    
    @property
    def extra_model_paths(self):
        return f'{self.workflow_dir}/extra_model_paths.yaml'


    def _clone_main_module(self):

        if os.path.exists(self.main_module_dir):
            # remove existing directory
            
            if os.path.isfile(self.main_module_dir) or os.path.islink(self.main_module_dir):
                os.remove(self.main_module_dir)
            elif os.path.isdir(self.main_module_dir):
                shutil.rmtree(self.main_module_dir)
            else:
                raise ValueError(f'Invalid file type: {self.main_module_dir}')

        main_module = self.dependency_config.base_code
        run_command(["git", "clone", main_module.github_url, self.main_module_dir])
        run_command(["git", "checkout", main_module.commit_sha], cwd=self.main_module_dir)

    def prepare_workspace(self, inventory: Inventory):
        """ Prepare directory structure for the workflow
        Use (symplink) dependencies from the inventory (also validate the dependencies are correct)
        """
        # TODO: validate workspace
        _validate_dir(self.workflow_dir)
        _validate_dir(f'{self.input_dir}', create=True)
        _validate_dir(f'{self.output_dir}', create=True)
        _validate_dir(f'{self.temp_dir}', create=True)


        # Customer Modules
        def _check_code_module(existing_code_module, required_code_module):
            # compare the two code modules are the same
            assert existing_code_module.name == required_code_module.name, 'Name does not match'
            assert existing_code_module.github_url == required_code_module.github_url, 'Github url does not match'
            assert existing_code_module.commit_sha == required_code_module.commit_sha, 'Commit sha does not match'
            return True
        
        assert _check_code_module(
            existing_code_module=inventory.base_code,
            required_code_module=self.dependency_config.base_code
        ), 'Base code module does not match'
        # clone ComfyUI base repo
        self._clone_main_module()

        for custom_node in self.dependency_config.custom_nodes:
            inventory.check_module_exist(custom_node.name)
            assert _check_code_module(
                existing_code_module=inventory.modules[custom_node.name],
                required_code_module=custom_node
            ), f'Custom node {custom_node.name} does not match'
            
        # Create symbolic link to custom modules
        # TODO: create virtual inventory if necessary in the future
        custom_modules = [f.path for f in os.scandir(inventory.workspace.module_path) if f.is_dir()]
        for module in custom_modules:
            _create_symlink(
                src=module, 
                dst=f'{self.main_module_dir}/custom_nodes/{os.path.basename(module)}')


        # Custom models
        def _check_model(existing_model, required_model):
            # compare the two models are the same
            assert existing_model.name == required_model.name, 'Name does not match'
            assert existing_model.file_name == required_model.file_name, 'File name does not match'
            assert existing_model.rel_file_path == required_model.rel_file_path, 'Rel file path does not match'
            assert existing_model.category == required_model.category, 'Category does not match'
            return True

        
        # FIXME: workflow should provide an inclusive list of custom models
        # FIXME: install model to inventory on demand 
        # for the time being, we assume all models in the custom_model_dir are used
        self.dependency_config.custom_models = [model for _, model in inventory.models.values()] 

        for custom_model in self.dependency_config.custom_models:
            inventory.check_model_exist(custom_model.rel_file_path)
            _, model_dependency = inventory.models[custom_model.rel_file_path]
            assert _check_model(model_dependency, custom_model), f'Custom model {custom_model.rel_file_path} does not match'

        # Create symbolic link to custom models
        for model in self.dependency_config.custom_models:
            _create_symlink(
                src=f'{inventory.workspace.model_path}/{model.rel_file_path}', 
                dst=f'{self.main_module_dir}/models/{model.rel_file_path}')
        

        with open(f'{self.workflow_dir}/manifest.json', 'w') as f:
            f.write(self.model_dump_json())

        import yaml
        

        extra_model_paths_config = {
            'comfyui': {
                'base_path': f'{self.workflow_dir}/ComfyUI',
                # 'custom_nodes': f'{self.custom_node_dir}',
                # 'checkpoints': f'{self.custom_model_dir}/checkpoints/',
                # 'clip': f'{self.custom_model_dir}/clip/',
                # 'clip_vision': f'{self.custom_model_dir}/clip_vision/',
                # 'configs': f'{self.custom_model_dir}/configs/',
                # 'controlnet': f'{self.custom_model_dir}/controlnet/',
                # 'embeddings': f'{self.custom_model_dir}/embeddings/',
                # 'loras': f'{self.custom_model_dir}/loras/',
                # 'upscale_models': f'{self.custom_model_dir}/upscale_models/',
                # 'vae': f'{self.custom_model_dir}/vae/'
            }
        } 

        # FIXME: list all subfolders in the custom_model_dir
        # for model_category in os.listdir(self.custom_model_dir):
        #     if os.path.isdir(os.path.join(self.custom_model_dir, model_category)):
        #         print(f'Found model category: {model_category}')
        #         extra_model_paths_config['comfyui'][model_category] = f'{self.custom_model_dir}/{model_category}/'

        with open(self.extra_model_paths, 'w') as f:
            yaml_data = yaml.dump(extra_model_paths_config, default_flow_style=False)
            f.write(yaml_data)
        

def reconstruct_inventory(base_path):
    # build inventory

    import os
    import subprocess

    workspace = Workspace(base_path=base_path)
    
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
    
    modules_base_path = workspace.module_path 
    for sub_dir in os.listdir(modules_base_path):
        if os.path.isdir(os.path.join(modules_base_path, sub_dir)):
            if sub_dir == '__pycache__':
                continue

            modules[sub_dir] = reconstruct_module(os.path.join(modules_base_path, sub_dir))

    models = {}
    models_base_path = workspace.model_path 
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
        workspace=workspace,
        base_code=reconstruct_module(workspace.base_code_path),
        modules=modules,
        models=models)

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
            "commit_sha": "f1c2301697cb1cd538f8d4190741935548bb6734",
        })
    
    models = []
    modules = []
    with open(f'{base_path}/dependency.json', 'r') as f:
        dependency = json.load(f)
        for m in dependency['models']:
            models.append(ModelDependency(**m))
        for m in dependency['modules']:
            modules.append(CodeDependency(**m))
    
    dependency_config = ComfyUIDependencyConfig(
                            base_code=code, 
                            custom_nodes=modules, 
                            custom_models=models)

    workflow = Workflow(
        id=str(uuid.uuid4()),
        name="all_in_one_controlnet", 
        category="comfyui",
        description="Example workflow for comfyui", 
        workflow_dir=base_path,
        python_venv=RuntimeEnv(venv_path="/home/ruoyu.huang/workspace/xiaoapp/venv"),
        dependency_config=dependency_config
    )
    
    return workflow


def get_workflow_manifest(workflow_dir: str):
    manifest_path = f'{workflow_dir}/manifest.json'
    with open(manifest_path, 'r') as f:
        workflow_to_run = Workflow.model_validate(json.load(f))
        return workflow_to_run