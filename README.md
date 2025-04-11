[![Test status](https://github.com/apartmentlines/runpod-singleton/actions/workflows/python-app.yml/badge.svg)](https://github.com/apartmentlines/runpod-singleton/actions/workflows/python-app.yml)
[![CodeQL](https://github.com/apartmentlines/runpod-singleton/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/apartmentlines/runpod-singleton/actions/workflows/github-code-scanning/codeql)

<div align="center">
  <img src="logo.png" alt="runpod-singleton logo">
</div>

# RunPod Singleton Manager

A Python utility to manage a single, persistent [RunPod](https://www.runpod.io) pod instance based on a configuration file. It ensures that a pod with a specific name exists and is running.

## Purpose

This tool simplifies the management of a dedicated [RunPod](https://www.runpod.io) pod. It automates the following tasks:

1. **Check Existence:** Verifies if a pod with the configured name already exists.
2. **Check Status:** If the pod exists, checks if it's running.
3. **Start Stopped Pod:** If the pod exists but is stopped, it attempts to resume it.
4. **Terminate Failed Starts:** If the pod fails to restart (e.g. no available GPUs) it attempts to terminate it.
4. **Create New Pod:** If the pod doesn't exist, it attempts to create a new one using a prioritized list of GPU types specified in the configuration. It iterates through the list until a pod is successfully created or all options are exhausted.
5. **Retry Logic:** Includes basic retry logic for pod creation attempts.

This is useful for scenarios where you need a specific pod configuration to be intermittently available. In particular, it allows you resume the pod without worrying about GPU availability.

## Requirements

* [Python](https://www.python.org) 3.10+

## Installation

You can install the package using pip:

```bash
pip install .
```

Alternatively, for development:

```bash
pip install -e .[dev]
```

## Usage

### Command line

The primary way to use the tool is via the command-line script `runpod-singleton`.

```bash
runpod-singleton <path_to_config.yaml> [--api-key YOUR_API_KEY] [--count | --stop --terminate] [--debug]
```

**Note:** If both `--stop` and `--terminate` are provided, the script will first attempt to stop any running matching pods, and then attempt to terminate all matching pods before exiting.

For more details, run with the `--help` argument.


**Example:**

```bash
# Default mode: Ensure one pod is running
# API key can also be passed via the RUNPOD_API_KEY environment variable.
# The script will exit with code `0` if a pod matching the configuration
# is successfully running at the end of the execution, and `1` otherwise.
runpod-singleton config.yaml --api-key $RUNPOD_API_KEY --debug

# Count existing pods
runpod-singleton config.yaml --count

# Stop/terminate running pods matching the name
runpod-singleton config.yaml --stop
runpod-singleton config.yaml --terminate
runpod-singleton config.yaml --stop --terminate
```


### Programmatic Usage

You can also use the `RunpodSingletonManager` class directly within your Python scripts for more complex integrations or automation tasks.

**Example:**

```python
import os
from pathlib import Path
from runpod_singleton import RunpodSingletonManager

# Define the path to your configuration file.
config_file_path = Path("path/to/your/config.yaml")

api_key = os.getenv("MY_API_KEY")

# --- Manage Mode (Default: ensure pod is running) ---
print("Attempting to manage the pod...")
manager = RunpodSingletonManager(
    config_path=config_file_path,
    # If no api_key argument is provided, the RUNPOD_API_KEY environment variable will be used.
    api_key=api_key,
    # stop=False, # Default
    # terminate=False, # Default
    debug=True # Optional: enable debug logging
)
result = manager.run() # Returns pod ID on success, None on failure

if result:
    print(f"Pod management successful. Pod ID: {result}")
else:
    print(f"Pod management failed.")

# --- Count Mode ---
print("\nAttempting to count matching pods...")
try:
    count_manager = RunpodSingletonManager(
        config_path=config_file_path,
        api_key=api_key,
        debug=True
    )
    counts = count_manager.count_pods()
    if counts:
      print(f"Pod counts: Total={counts['total']}, Running={counts['running']}")
except Exception as e:
    print(f"Failed to retrieve pod counts: {e}")

# --- Cleanup Mode (Example: Stop and Terminate) ---
print("\nAttempting to stop and terminate matching pods...")
cleanup_manager = RunpodSingletonManager(
    config_path=config_file_path,
    api_key=api_key,
    stop=True,
    terminate=True,
    debug=True
)
cleanup_result = cleanup_manager.run() # Returns True on success, None on failure

if cleanup_result:
    print("Cleanup actions completed successfully.")
else:
    print(f"Cleanup actions failed.")
```


## Configuration

The behavior of the script is controlled by a YAML configuration file. See [sample.config.yaml](sample.config.yaml) for a detailed template with explanations for all available options.

**Example `config.yaml`:**

```yaml
# config.yaml
pod_name: my-worker-pod
image_name: my-dockerhub-user/my-worker-image:latest
gpu_types:
  - "NVIDIA GeForce RTX 3090"
  - "NVIDIA RTX A5000"
cloud_type: SECURE
gpu_count: 1
container_disk_in_gb: 50
ports: "8080/http"
env:
  WORKER_MODE: "production"
  API_SECRET: !ENV ${MY_API_SECRET_ENV_VAR} # Loads from environment variable
```

## Environment Variables

*   `RUNPOD_API_KEY`: Your [RunPod API key](https://www.runpod.io/console/user/settings). Can be used instead of the `--api-key` argument.
*   Configuration file environment variables: If you use the `!ENV ${VAR_NAME}` syntax in your `config.yaml`, the corresponding environment variables must be set when running the script.
