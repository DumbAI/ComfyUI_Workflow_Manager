# Development thesis

An open source framework to manage and run AI native workflows. 

The framework is easy to use on home laptops (Mac, Windows), also easy to deploy to kubenete cluster and be used in a production environment.

The framework should use existing building block, primarily ComfyUI, to offer low-code app building experience.

The framework should expand ComfyUI and offer building blocks to build AI native App for text, doc and audio processing.

The framework should make it easy to package and distribute via an app store.

The framework should offer native eval components for AI app (validation, human review, accuracy dashboard)

The framework should able to run workflow in two mode: mutable (interactive) and immutable

The framework should run workflows in parallel, and manage a worker pool

The framework should be able to run workflow in remote machine (how??? Skypilot?)

The framework UI should show status of all worker, including CPU, GPU, Mem utilization



# Work log

## 7/19
Test workflow
```
cd py
PYTHONPATH=$(pwd) python workflow/controller.py
```

Manual Step 
* Tune on Dev mode, save workflow API format
* Display node ID: https://www.reddit.com/r/comfyui/comments/1aotb3w/which_custom_node_shows_the_node_id_number_on/

## 8/4
Basic UI function to mange workflows

# 8/12
Add data abstraction for inventory and workflow


## 8/17
build database

```
python -m workflow.state_manager
```
