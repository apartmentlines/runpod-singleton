"""Constants used across the runpod-singleton package."""

# Configuration Keys
POD_NAME = "pod_name"
IMAGE_NAME = "image_name"
GPU_TYPES = "gpu_types"
CLOUD_TYPE = "cloud_type"
SUPPORT_PUBLIC_IP = "support_public_ip"
START_SSH = "start_ssh"
DATA_CENTER_ID = "data_center_id"
COUNTRY_CODE = "country_code"
GPU_COUNT = "gpu_count"
VOLUME_IN_GB = "volume_in_gb"
CONTAINER_DISK_IN_GB = "container_disk_in_gb"
MIN_VCPU_COUNT = "min_vcpu_count"
MIN_MEMORY_IN_GB = "min_memory_in_gb"
DOCKER_ARGS = "docker_args"
PORTS = "ports"
VOLUME_MOUNT_PATH = "volume_mount_path"
ENV = "env"
TEMPLATE_ID = "template_id"
NETWORK_VOLUME_ID = "network_volume_id"
ALLOWED_CUDA_VERSIONS = "allowed_cuda_versions"
MIN_DOWNLOAD = "min_download"
MIN_UPLOAD = "min_upload"

# Runpod API Response Keys / Values
POD_ID = "id"
POD_STATUS = "desiredStatus"
POD_MACHINE = "machine"
POD_GPU_DISPLAY_NAME = "gpuDisplayName"
POD_GPU_COUNT = "gpuCount"
POD_NAME_API = "name"
POD_STATUS_RUNNING = "RUNNING"
POD_STATUS_EXITED = "EXITED"

# Default Values
DEFAULT_CLOUD_TYPE = "ALL"
DEFAULT_SUPPORT_PUBLIC_IP = True
DEFAULT_START_SSH = True
DEFAULT_GPU_COUNT = 1
DEFAULT_VOLUME_IN_GB = 0
DEFAULT_MIN_VCPU_COUNT = 1
DEFAULT_MIN_MEMORY_IN_GB = 1
DEFAULT_DOCKER_ARGS = ""
DEFAULT_VOLUME_MOUNT_PATH = "/runpod-volume"

# Exit Codes
EXIT_SUCCESS = 0
EXIT_FAILURE = 1

# Retry values
DEFAULT_CREATE_GPU_RETRIES = 1
DEFAULT_CREATE_RETRY_WAIT_SECONDS = 10

# Callback Server Defaults
DEFAULT_TEST_CALLBACK_HOST = "127.0.0.1"
DEFAULT_TEST_CALLBACK_PORT = 8080
