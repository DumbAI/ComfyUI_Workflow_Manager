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


# Work with workspace

sqlite3 your_database.db

```
.tables

select * from workflowrecord;

.quit
```