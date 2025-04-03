# RunPod Singleton Manager

A Python utility to manage a single, persistent RunPod pod instance based on a configuration file. It ensures that a pod with a specific name exists and is running.

## Purpose

This tool simplifies the management of a dedicated RunPod pod. It automates the following tasks:

1.  **Check Existence:** Verifies if a pod with the configured name already exists.
2.  **Check Status:** If the pod exists, checks if it's running.
3.  **Start Stopped Pod:** If the pod exists but is stopped, it attempts to resume it.
4.  **Create New Pod:** If the pod doesn't exist, it attempts to create a new one using a prioritized list of GPU types specified in the configuration. It iterates through the list until a pod is successfully created or all options are exhausted.
5.  **Retry Logic:** Includes basic retry logic for pod creation attempts.

This is useful for scenarios where you need a specific pod configuration to be consistently available without manual intervention.

## Installation

You can install the package using pip:

```bash
# Ensure you have Python 3.10+
pip install .
```

Alternatively, for development:

```bash
pip install -e .[dev]
```

## Usage

The primary way to use the tool is via the command-line script `runpod-singleton`.

```bash
runpod-singleton <path_to_config.yaml> [--api-key YOUR_API_KEY] [--stop] [--terminate] [--debug]
```

**Note:** If both `--stop` and `--terminate` are provided, the script will first attempt to stop any running matching pods, and then attempt to terminate all matching pods before exiting.

For more details, run with the `--help` argument.


**Example:**

```bash
# API key can also be passed via the RUNPOD_API_KEY environment variable.
runpod-singleton config.yaml --api-key $RUNPOD_API_KEY --debug
```

The script will exit with code `0` if a pod matching the configuration is successfully running at the end of the execution, and `1` otherwise.

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

*   `RUNPOD_API_KEY`: Your RunPod API key. Can be used instead of the `--api-key` argument.
*   Configuration file environment variables: If you use the `!ENV ${VAR_NAME}` syntax in your `config.yaml`, the corresponding environment variables must be set when running the script.
