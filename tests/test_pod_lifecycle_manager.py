import pytest
import logging
from unittest.mock import MagicMock, call, patch
from typing import Any

# Import the classes to be tested/mocked
from runpod_singleton.singleton import RunpodApiClient, PodLifecycleManager
from runpod_singleton import constants as const


# --- Fixtures ---

@pytest.fixture
def mock_api_client() -> MagicMock:
    """Fixture for a mocked RunpodApiClient."""
    return MagicMock(spec=RunpodApiClient)


@pytest.fixture
def mock_logger() -> MagicMock:
    """Fixture for a mocked Logger."""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Fixture for a sample configuration dictionary."""
    return {
        const.POD_NAME: "test-singleton-pod",
        const.IMAGE_NAME: "test-image",
        const.GPU_TYPES: ["NVIDIA GeForce RTX 3090", "NVIDIA GeForce RTX 4090"],
        const.GPU_COUNT: 1,
        const.CONTAINER_DISK_IN_GB: 10,
    }


@pytest.fixture
def pod_lifecycle_manager(
    mock_api_client: MagicMock, sample_config: dict[str, Any], mock_logger: MagicMock
) -> PodLifecycleManager:
    """Fixture to create a PodLifecycleManager instance with mocks."""
    return PodLifecycleManager(
        client=mock_api_client,
        config=sample_config,
        logger=mock_logger,
        stop=False,
        terminate=False,
    )


@pytest.fixture
def pod_lifecycle_manager_stop(
    mock_api_client: MagicMock, sample_config: dict[str, Any], mock_logger: MagicMock
) -> PodLifecycleManager:
    """Fixture for PodLifecycleManager with stop=True."""
    return PodLifecycleManager(
        client=mock_api_client,
        config=sample_config,
        logger=mock_logger,
        stop=True,
        terminate=False,
    )


@pytest.fixture
def pod_lifecycle_manager_terminate(
    mock_api_client: MagicMock, sample_config: dict[str, Any], mock_logger: MagicMock
) -> PodLifecycleManager:
    """Fixture for PodLifecycleManager with terminate=True."""
    return PodLifecycleManager(
        client=mock_api_client,
        config=sample_config,
        logger=mock_logger,
        stop=False,
        terminate=True,
    )


@pytest.fixture
def pod_lifecycle_manager_stop_terminate(
    mock_api_client: MagicMock, sample_config: dict[str, Any], mock_logger: MagicMock
) -> PodLifecycleManager:
    """Fixture for PodLifecycleManager with stop=True and terminate=True."""
    return PodLifecycleManager(
        client=mock_api_client,
        config=sample_config,
        logger=mock_logger,
        stop=True,
        terminate=True,
    )


# --- Helper Data ---

POD_ID_1 = "pod_id_1"
POD_ID_2 = "pod_id_2"
POD_NAME = "test-singleton-pod"
OTHER_POD_NAME = "other-pod"

RUNNING_POD = {
    const.POD_ID: POD_ID_1,
    const.POD_NAME_API: POD_NAME,
    const.POD_STATUS: const.POD_STATUS_RUNNING,
    const.GPU_COUNT: 1,
}
STOPPED_POD = {
    const.POD_ID: POD_ID_1,
    const.POD_NAME_API: POD_NAME,
    const.POD_STATUS: const.POD_STATUS_EXITED,
    const.GPU_COUNT: 0,
}
OTHER_RUNNING_POD = {
    const.POD_ID: POD_ID_2,
    const.POD_NAME_API: OTHER_POD_NAME,
    const.POD_STATUS: const.POD_STATUS_RUNNING,
    const.GPU_COUNT: 1,
}
MATCHING_STOPPED_POD_2 = {
    const.POD_ID: POD_ID_2,
    const.POD_NAME_API: POD_NAME,
    const.POD_STATUS: const.POD_STATUS_EXITED,
    const.GPU_COUNT: 0,
}


# --- Test Cases ---

def test_init(
    mock_api_client: MagicMock, sample_config: dict[str, Any], mock_logger: MagicMock
):
    """Test PodLifecycleManager initialization."""
    manager = PodLifecycleManager(
        client=mock_api_client,
        config=sample_config,
        logger=mock_logger,
        stop=True,
        terminate=False,
    )
    assert manager.client is mock_api_client
    assert manager.config is sample_config
    assert manager.log is mock_logger
    assert manager.stop is True
    assert manager.terminate is False
    assert manager.pod_name == sample_config[const.POD_NAME]


def test_get_all_pods_from_api(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test _get_all_pods_from_api calls client.get_pods."""
    expected_pods = [RUNNING_POD, OTHER_RUNNING_POD]
    mock_api_client.get_pods.return_value = expected_pods
    pods = pod_lifecycle_manager._get_all_pods_from_api()
    mock_api_client.get_pods.assert_called_once()
    assert pods == expected_pods


def test_get_all_pods_from_api_failure(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test _get_all_pods_from_api returns None and logs error on API failure."""
    error_message = "API connection failed"
    mock_api_client.get_pods.side_effect = Exception(error_message)
    pods = pod_lifecycle_manager._get_all_pods_from_api()
    mock_api_client.get_pods.assert_called_once()
    assert pods is None
    mock_logger.error.assert_called_once_with(
        f"Failed to retrieve pods from RunPod API: {error_message}"
    )


def test_find_first_pod_by_name_found(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test find_first_pod_by_name finds the correct pod."""
    mock_api_client.get_pods.return_value = [OTHER_RUNNING_POD, RUNNING_POD]
    found_pod = pod_lifecycle_manager.find_first_pod_by_name()
    mock_api_client.get_pods.assert_called_once()
    assert found_pod == RUNNING_POD


def test_find_first_pod_by_name_not_found(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test find_first_pod_by_name returns {} when no match."""
    mock_api_client.get_pods.return_value = [OTHER_RUNNING_POD]
    found_pod = pod_lifecycle_manager.find_first_pod_by_name()
    mock_api_client.get_pods.assert_called_once()
    assert found_pod == {}


def test_find_first_pod_by_name_api_failure(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test find_first_pod_by_name returns None when API fails."""
    error_message = "API connection failed during find first"
    mock_api_client.get_pods.side_effect = Exception(error_message)
    found_pod = pod_lifecycle_manager.find_first_pod_by_name()
    mock_api_client.get_pods.assert_called_once()
    assert found_pod is None
    mock_logger.error.assert_any_call(
        f"Failed to retrieve pods from RunPod API: {error_message}"
    )
    mock_logger.error.assert_any_call(
        "API call to get pods failed. Cannot search for pod."
    )


def test_find_all_pods_by_name_found(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test find_all_pods_by_name finds all matching pods."""
    mock_api_client.get_pods.return_value = [
        RUNNING_POD,
        OTHER_RUNNING_POD,
        MATCHING_STOPPED_POD_2,
    ]
    found_pods = pod_lifecycle_manager.find_all_pods_by_name()
    mock_api_client.get_pods.assert_called_once()
    assert len(found_pods) == 2
    assert RUNNING_POD in found_pods
    assert MATCHING_STOPPED_POD_2 in found_pods


def test_find_all_pods_by_name_not_found(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test find_all_pods_by_name returns empty list when no match."""
    mock_api_client.get_pods.return_value = [OTHER_RUNNING_POD]
    found_pods = pod_lifecycle_manager.find_all_pods_by_name()
    mock_api_client.get_pods.assert_called_once()
    assert found_pods == []


def test_find_all_pods_by_name_api_failure(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test find_all_pods_by_name returns None when API fails."""
    error_message = "API connection failed during find all"
    mock_api_client.get_pods.side_effect = Exception(error_message)
    found_pods = pod_lifecycle_manager.find_all_pods_by_name()
    mock_api_client.get_pods.assert_called_once()
    assert found_pods is None
    # Check that the error from _get_all_pods_from_api was logged
    mock_logger.error.assert_any_call(
        f"Failed to retrieve pods from RunPod API: {error_message}"
    )
    # Check that the error from find_all_pods_by_name itself was logged
    mock_logger.error.assert_any_call(
        "API call to get pods failed. Cannot find matching pods."
    )


# --- manage() Tests ---

def test_manage_pod_exists_running(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test manage() when a matching running pod exists."""
    mock_api_client.get_pods.return_value = [RUNNING_POD]
    result = pod_lifecycle_manager.manage()
    mock_api_client.get_pods.assert_called_once()
    # Expect _handle_existing_pod to be called, which should return the pod ID for a running pod
    mock_api_client.resume_pod.assert_not_called()
    mock_api_client.create_pod.assert_not_called()
    mock_api_client.terminate_pod.assert_not_called()
    assert result == RUNNING_POD[const.POD_ID]


def test_manage_pod_exists_stopped_resumes_successfully(
    pod_lifecycle_manager: PodLifecycleManager,
    mock_api_client: MagicMock,
    sample_config: dict[str, Any],
):
    """Test manage() when a stopped pod exists and resumes successfully."""
    mock_api_client.get_pods.return_value = [STOPPED_POD]
    mock_api_client.resume_pod.return_value = {"id": POD_ID_1, "desiredStatus": const.POD_STATUS_RUNNING} # Simulate resume success
    # Mock get_pod called by _handle_existing_pod after resume attempt
    mock_api_client.get_pod.return_value = {**STOPPED_POD, const.POD_STATUS: const.POD_STATUS_RUNNING}

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    mock_api_client.resume_pod.assert_called_once_with(
        POD_ID_1, gpu_count=sample_config[const.GPU_COUNT]
    )
    mock_api_client.get_pod.assert_called_once_with(POD_ID_1)
    mock_api_client.create_pod.assert_not_called()
    mock_api_client.terminate_pod.assert_not_called()
    assert result == STOPPED_POD[const.POD_ID]


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_pod_exists_stopped_resume_fails_api_error_creates_new(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any]
):
    """Test manage() terminates and creates new pod if resume fails (API error)."""
    gpu_type_1 = sample_config[const.GPU_TYPES][0]
    mock_api_client.get_pods.return_value = [STOPPED_POD]
    mock_api_client.resume_pod.side_effect = Exception("API Error") # Simulate resume failure

    # Mock successful creation after resume failure
    new_pod_id = "new_pod_after_fail"
    mock_api_client.create_pod.return_value = {"id": new_pod_id}
    mock_api_client.get_pod.return_value = { # Mock validation call for the new pod
        const.POD_ID: new_pod_id,
        const.POD_NAME_API: sample_config[const.POD_NAME],
        const.POD_STATUS: const.POD_STATUS_RUNNING,
    }

    result = pod_lifecycle_manager.manage()

    # Assertions for failed resume part
    mock_api_client.get_pods.assert_called_once()
    mock_api_client.resume_pod.assert_called_once_with(POD_ID_1, gpu_count=sample_config[const.GPU_COUNT])
    mock_api_client.terminate_pod.assert_called_once_with(POD_ID_1) # Should terminate failed pod

    # Assertions for successful creation part
    expected_create_args = {
        "name": sample_config[const.POD_NAME], "image_name": sample_config[const.IMAGE_NAME], "gpu_type_id": gpu_type_1,
        "gpu_count": sample_config[const.GPU_COUNT], "container_disk_in_gb": sample_config[const.CONTAINER_DISK_IN_GB],
        "cloud_type": const.DEFAULT_CLOUD_TYPE, "support_public_ip": const.DEFAULT_SUPPORT_PUBLIC_IP, "start_ssh": const.DEFAULT_START_SSH,
        "volume_in_gb": const.DEFAULT_VOLUME_IN_GB, "min_vcpu_count": const.DEFAULT_MIN_VCPU_COUNT, "min_memory_in_gb": const.DEFAULT_MIN_MEMORY_IN_GB,
        "docker_args": const.DEFAULT_DOCKER_ARGS, "volume_mount_path": const.DEFAULT_VOLUME_MOUNT_PATH,
    }
    mock_api_client.create_pod.assert_called_once_with(**expected_create_args)
    # get_pod should be called once for the new pod validation
    mock_api_client.get_pod.assert_called_once_with(new_pod_id)

    assert result == new_pod_id


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_pod_exists_stopped_resume_fails_validation_creates_new(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any]
):
    """Test manage() terminates and creates new pod if resume validation fails."""
    gpu_type_1 = sample_config[const.GPU_TYPES][0]
    mock_api_client.get_pods.return_value = [STOPPED_POD]
    mock_api_client.resume_pod.return_value = {"id": POD_ID_1, "desiredStatus": "RESTARTING"} # API returns intermediate status
    # Mock get_pod called by _handle_existing_pod shows it's still not running
    mock_get_pod_validation_fail = {**STOPPED_POD, const.POD_STATUS: "RESTARTING"}

    # Mock successful creation after resume failure
    new_pod_id = "new_pod_after_fail_2"
    mock_create_pod_success = {"id": new_pod_id}
    mock_get_pod_validation_success = { # Mock validation call for the new pod
        const.POD_ID: new_pod_id,
        const.POD_NAME_API: sample_config[const.POD_NAME],
        const.POD_STATUS: const.POD_STATUS_RUNNING,
    }
    # get_pod will be called twice: once for resume validation (fail), once for create validation (success)
    mock_api_client.get_pod.side_effect = [mock_get_pod_validation_fail, mock_get_pod_validation_success]
    mock_api_client.create_pod.return_value = mock_create_pod_success

    result = pod_lifecycle_manager.manage()

    # Assertions for failed resume part
    mock_api_client.get_pods.assert_called_once()
    mock_api_client.resume_pod.assert_called_once_with(POD_ID_1, gpu_count=sample_config[const.GPU_COUNT])
    mock_api_client.terminate_pod.assert_called_once_with(POD_ID_1) # Should terminate failed pod

    # Assertions for successful creation part
    expected_create_args = {
        "name": sample_config[const.POD_NAME], "image_name": sample_config[const.IMAGE_NAME], "gpu_type_id": gpu_type_1,
        "gpu_count": sample_config[const.GPU_COUNT], "container_disk_in_gb": sample_config[const.CONTAINER_DISK_IN_GB],
        "cloud_type": const.DEFAULT_CLOUD_TYPE, "support_public_ip": const.DEFAULT_SUPPORT_PUBLIC_IP, "start_ssh": const.DEFAULT_START_SSH,
        "volume_in_gb": const.DEFAULT_VOLUME_IN_GB, "min_vcpu_count": const.DEFAULT_MIN_VCPU_COUNT, "min_memory_in_gb": const.DEFAULT_MIN_MEMORY_IN_GB,
        "docker_args": const.DEFAULT_DOCKER_ARGS, "volume_mount_path": const.DEFAULT_VOLUME_MOUNT_PATH,
    }
    mock_api_client.create_pod.assert_called_once_with(**expected_create_args)
    # get_pod should be called twice
    assert mock_api_client.get_pod.call_count == 2
    mock_api_client.get_pod.assert_has_calls([call(POD_ID_1), call(new_pod_id)])

    assert result == new_pod_id


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_no_pod_creates_successfully(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any]
):
    """Test manage() creates a pod when none exists."""
    gpu_type_1, gpu_type_2 = sample_config[const.GPU_TYPES]
    mock_api_client.get_pods.return_value = [] # No existing pods
    # Simulate create_pod succeeding on the first try
    created_pod_id = "new_pod_id"
    mock_api_client.create_pod.return_value = {"id": created_pod_id}
    # Simulate get_pod for validation succeeding
    mock_api_client.get_pod.return_value = {
        const.POD_ID: created_pod_id,
        const.POD_NAME_API: sample_config[const.POD_NAME],
        const.POD_STATUS: const.POD_STATUS_RUNNING, # Assume it becomes running quickly
    }

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    mock_api_client.resume_pod.assert_not_called()
    # Check create_pod was called with correct args for the first GPU type
    expected_create_args = {
        "name": sample_config[const.POD_NAME],
        "image_name": sample_config[const.IMAGE_NAME],
        "gpu_type_id": gpu_type_1,
        "gpu_count": sample_config[const.GPU_COUNT],
        "container_disk_in_gb": sample_config[const.CONTAINER_DISK_IN_GB],
        # Add defaults or other expected args based on implementation
        "cloud_type": const.DEFAULT_CLOUD_TYPE,
        "support_public_ip": const.DEFAULT_SUPPORT_PUBLIC_IP,
        "start_ssh": const.DEFAULT_START_SSH,
        "volume_in_gb": const.DEFAULT_VOLUME_IN_GB,
        "min_vcpu_count": const.DEFAULT_MIN_VCPU_COUNT,
        "min_memory_in_gb": const.DEFAULT_MIN_MEMORY_IN_GB,
        "docker_args": const.DEFAULT_DOCKER_ARGS,
        "volume_mount_path": const.DEFAULT_VOLUME_MOUNT_PATH,
    }
    mock_api_client.create_pod.assert_called_once_with(**expected_create_args)
    mock_api_client.get_pod.assert_called_once_with(created_pod_id) # Validation call
    mock_api_client.terminate_pod.assert_not_called()
    assert result == created_pod_id


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_no_pod_creation_fails_first_succeeds_second(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any]
):
    """Test manage() tries next GPU if first create fails, succeeds on second."""
    gpu_type_1, gpu_type_2 = sample_config[const.GPU_TYPES]
    mock_api_client.get_pods.return_value = [] # No existing pods
    # Simulate create_pod failing on first GPU, succeeding on second
    created_pod_id = "new_pod_id_2"
    mock_api_client.create_pod.side_effect = [
        Exception("GPU unavailable"), # Fails for gpu_type_1
        {"id": created_pod_id}        # Succeeds for gpu_type_2
    ]
    # Simulate get_pod for validation succeeding
    mock_api_client.get_pod.return_value = {
        const.POD_ID: created_pod_id,
        const.POD_NAME_API: sample_config[const.POD_NAME],
        const.POD_STATUS: const.POD_STATUS_RUNNING,
    }

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    assert mock_api_client.create_pod.call_count == 2
    # Check first call args
    expected_create_args_1 = {
        "name": sample_config[const.POD_NAME], "image_name": sample_config[const.IMAGE_NAME], "gpu_type_id": gpu_type_1,
        "gpu_count": sample_config[const.GPU_COUNT], "container_disk_in_gb": sample_config[const.CONTAINER_DISK_IN_GB],
        "cloud_type": const.DEFAULT_CLOUD_TYPE, "support_public_ip": const.DEFAULT_SUPPORT_PUBLIC_IP, "start_ssh": const.DEFAULT_START_SSH,
        "volume_in_gb": const.DEFAULT_VOLUME_IN_GB, "min_vcpu_count": const.DEFAULT_MIN_VCPU_COUNT, "min_memory_in_gb": const.DEFAULT_MIN_MEMORY_IN_GB,
        "docker_args": const.DEFAULT_DOCKER_ARGS, "volume_mount_path": const.DEFAULT_VOLUME_MOUNT_PATH,
    }
    # Check second call args
    expected_create_args_2 = {
        "name": sample_config[const.POD_NAME], "image_name": sample_config[const.IMAGE_NAME], "gpu_type_id": gpu_type_2,
        "gpu_count": sample_config[const.GPU_COUNT], "container_disk_in_gb": sample_config[const.CONTAINER_DISK_IN_GB],
        "cloud_type": const.DEFAULT_CLOUD_TYPE, "support_public_ip": const.DEFAULT_SUPPORT_PUBLIC_IP, "start_ssh": const.DEFAULT_START_SSH,
        "volume_in_gb": const.DEFAULT_VOLUME_IN_GB, "min_vcpu_count": const.DEFAULT_MIN_VCPU_COUNT, "min_memory_in_gb": const.DEFAULT_MIN_MEMORY_IN_GB,
        "docker_args": const.DEFAULT_DOCKER_ARGS, "volume_mount_path": const.DEFAULT_VOLUME_MOUNT_PATH,
    }
    mock_api_client.create_pod.assert_has_calls([
        call(**expected_create_args_1),
        call(**expected_create_args_2)
    ])
    mock_api_client.get_pod.assert_called_once_with(created_pod_id) # Validation call
    mock_api_client.terminate_pod.assert_not_called()
    assert result == created_pod_id


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_no_pod_creation_fails_all_gpus(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any]
):
    """Test manage() returns False if all GPU creation attempts fail."""
    mock_api_client.get_pods.return_value = [] # No existing pods
    # Simulate create_pod failing for all GPUs
    mock_api_client.create_pod.side_effect = Exception("GPU unavailable")

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    assert mock_api_client.create_pod.call_count == len(sample_config[const.GPU_TYPES]) # Called for each GPU type
    mock_api_client.get_pod.assert_not_called() # No validation needed
    mock_api_client.terminate_pod.assert_not_called()
    assert result is False


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_no_pod_creation_succeeds_but_validation_fails(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any]
):
    """Test manage() terminates pod if creation succeeds but validation fails."""
    # We only want one failure here, so limit to first GPU
    pod_lifecycle_manager.gpu_types = [sample_config[const.GPU_TYPES][0]]
    mock_api_client.get_pods.return_value = [] # No existing pods
    created_pod_id = "new_pod_id"
    mock_api_client.create_pod.return_value = {"id": created_pod_id}
    # Simulate get_pod for validation failing (e.g., wrong name or status)
    mock_api_client.get_pod.return_value = {
        const.POD_ID: created_pod_id,
        const.POD_NAME_API: "wrong-name", # Validation failure
        const.POD_STATUS: "DEAD",
    }

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    mock_api_client.create_pod.assert_called_once() # Only tries first GPU
    mock_api_client.get_pod.assert_called_once_with(created_pod_id) # Validation call
    mock_api_client.terminate_pod.assert_called_once_with(created_pod_id) # Should terminate failed validation
    assert result is False


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_api_failure_during_find(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test manage() returns False if the initial get_pods API call fails."""
    error_message = "Initial API Error during manage"
    # Simulate get_pods failing initially when called by find_first_pod_by_name
    mock_api_client.get_pods.side_effect = Exception(error_message)

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    mock_logger.error.assert_any_call(
        "API call to list pods failed during search. Cannot manage pod state."
    )
    mock_logger.error.assert_any_call(
        f"Failed to retrieve pods from RunPod API: {error_message}"
    )

    mock_api_client.create_pod.assert_not_called()
    mock_api_client.resume_pod.assert_not_called()
    mock_api_client.terminate_pod.assert_not_called()
    mock_api_client.get_pod.assert_not_called()

    assert result is False


@patch("runpod_singleton.singleton.time.sleep", return_value=None) # Mock time.sleep
def test_manage_no_pod_creation_retry_succeeds_same_gpu(
    mock_sleep, pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, sample_config: dict[str, Any], mock_logger: MagicMock
):
    """Test manage() retries creation on the same GPU and succeeds."""
    # Configure retries
    pod_lifecycle_manager.create_retries = 2
    gpu_type_1 = sample_config[const.GPU_TYPES][0]

    mock_api_client.get_pods.return_value = [] # No existing pods

    # Mock _create_pod_attempt to fail first time, succeed second time for gpu_type_1
    # Mock _validate_new_pod to succeed when creation succeeds
    created_pod_id = "new_pod_retry_id"
    mock_create_attempt = MagicMock(
        side_effect=[False, created_pod_id] # Fail first, succeed second
    )
    mock_validate = MagicMock(return_value=True)
    pod_lifecycle_manager._create_pod_attempt = mock_create_attempt
    pod_lifecycle_manager._validate_new_pod = mock_validate

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    assert mock_create_attempt.call_count == 2
    mock_create_attempt.assert_has_calls([call(gpu_type_1), call(gpu_type_1)])
    mock_validate.assert_called_once_with(created_pod_id)
    mock_sleep.assert_called_once_with(pod_lifecycle_manager.create_wait)
    assert result == created_pod_id


def test_manage_no_pod_empty_gpu_types_fails(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test manage() fails correctly if gpu_types list is empty."""
    pod_lifecycle_manager.gpu_types = [] # Override config
    mock_api_client.get_pods.return_value = [] # No existing pods

    result = pod_lifecycle_manager.manage()

    mock_api_client.get_pods.assert_called_once()
    mock_logger.error.assert_called_once_with(
        "No GPU types specified in configuration. Cannot create pod."
    )
    mock_api_client.create_pod.assert_not_called()
    assert result is False


# --- perform_cleanup_actions() Tests ---

def test_perform_cleanup_no_flags(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test cleanup does nothing if no flags are set."""
    # Setup manager with stop=False, terminate=False (default fixture)
    mock_api_client.get_pods.return_value = [RUNNING_POD, MATCHING_STOPPED_POD_2]
    result = pod_lifecycle_manager.perform_cleanup_actions()
    mock_api_client.get_pods.assert_called_once() # Still checks for pods
    mock_api_client.stop_pod.assert_not_called()
    mock_api_client.terminate_pod.assert_not_called()
    assert result is True # Cleanup itself didn't fail


def test_perform_cleanup_stop_flag(
    pod_lifecycle_manager_stop: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test cleanup stops only running matching pods with stop=True."""
    mock_api_client.get_pods.return_value = [RUNNING_POD, MATCHING_STOPPED_POD_2, OTHER_RUNNING_POD]
    result = pod_lifecycle_manager_stop.perform_cleanup_actions()
    mock_api_client.get_pods.assert_called_once()
    mock_api_client.stop_pod.assert_called_once_with(RUNNING_POD[const.POD_ID]) # Only the running one
    mock_api_client.terminate_pod.assert_not_called()
    assert result is True


def test_perform_cleanup_terminate_flag(
    pod_lifecycle_manager_terminate: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test cleanup terminates all matching pods with terminate=True."""
    mock_api_client.get_pods.return_value = [RUNNING_POD, MATCHING_STOPPED_POD_2, OTHER_RUNNING_POD]
    result = pod_lifecycle_manager_terminate.perform_cleanup_actions()
    mock_api_client.get_pods.assert_called_once()
    mock_api_client.stop_pod.assert_not_called()
    # Should terminate both matching pods regardless of state
    mock_api_client.terminate_pod.assert_has_calls(
        [call(RUNNING_POD[const.POD_ID]), call(MATCHING_STOPPED_POD_2[const.POD_ID])],
        any_order=True
    )
    assert mock_api_client.terminate_pod.call_count == 2
    assert result is True


def test_perform_cleanup_stop_and_terminate_flags(
    pod_lifecycle_manager_stop_terminate: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test cleanup stops running pods then terminates all matching pods."""
    mock_api_client.get_pods.return_value = [RUNNING_POD, MATCHING_STOPPED_POD_2, OTHER_RUNNING_POD]
    result = pod_lifecycle_manager_stop_terminate.perform_cleanup_actions()
    mock_api_client.get_pods.assert_called_once()
    # Stop should be called first only on the running one
    mock_api_client.stop_pod.assert_called_once_with(RUNNING_POD[const.POD_ID])
    # Terminate should be called on both matching pods
    mock_api_client.terminate_pod.assert_has_calls(
        [call(RUNNING_POD[const.POD_ID]), call(MATCHING_STOPPED_POD_2[const.POD_ID])],
        any_order=True
    )
    assert mock_api_client.terminate_pod.call_count == 2
    assert result is True


def test_perform_cleanup_no_matching_pods(
    pod_lifecycle_manager_stop_terminate: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test cleanup does nothing if no matching pods are found."""
    mock_api_client.get_pods.return_value = [OTHER_RUNNING_POD]
    result = pod_lifecycle_manager_stop_terminate.perform_cleanup_actions()
    mock_api_client.get_pods.assert_called_once()
    mock_api_client.stop_pod.assert_not_called()
    mock_api_client.terminate_pod.assert_not_called()
    assert result is True


def test_perform_cleanup_stop_api_error_continues(
    pod_lifecycle_manager_stop: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test cleanup logs error and continues if stop_pod API fails for one pod."""
    mock_api_client.get_pods.return_value = [RUNNING_POD, MATCHING_STOPPED_POD_2]
    error_message = "Stop API unavailable"
    mock_api_client.stop_pod.side_effect = Exception(error_message)

    result = pod_lifecycle_manager_stop.perform_cleanup_actions()

    mock_api_client.get_pods.assert_called_once()
    mock_api_client.stop_pod.assert_called_once_with(RUNNING_POD[const.POD_ID])
    mock_logger.error.assert_called_once_with(
        f"Error stopping pod {RUNNING_POD[const.POD_ID]}: {error_message}"
    )
    mock_api_client.terminate_pod.assert_not_called()
    assert result is True


def test_perform_cleanup_terminate_api_error_continues(
    pod_lifecycle_manager_terminate: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test cleanup logs error and continues if terminate_pod API fails for one pod."""
    mock_api_client.get_pods.return_value = [RUNNING_POD, MATCHING_STOPPED_POD_2]
    error_message = "Terminate API unavailable"
    mock_api_client.terminate_pod.side_effect = [Exception(error_message), MagicMock()] # Fail first, succeed second

    result = pod_lifecycle_manager_terminate.perform_cleanup_actions()

    mock_api_client.get_pods.assert_called_once()
    mock_api_client.stop_pod.assert_not_called()
    assert mock_api_client.terminate_pod.call_count == 2
    mock_api_client.terminate_pod.assert_has_calls(
        [call(RUNNING_POD[const.POD_ID]), call(MATCHING_STOPPED_POD_2[const.POD_ID])],
        any_order=True
    )
    mock_logger.error.assert_called_once_with(
        f"Error terminating pod {RUNNING_POD[const.POD_ID]}: {error_message}"
    )
    assert result is True


def test_perform_cleanup_api_failure(
    pod_lifecycle_manager_stop_terminate: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test cleanup returns False and logs error if find_all_pods_by_name fails."""
    error_message = "API Error during cleanup find"
    # Simulate get_pods failing when called by find_all_pods_by_name
    mock_api_client.get_pods.side_effect = Exception(error_message)

    result = pod_lifecycle_manager_stop_terminate.perform_cleanup_actions()

    mock_api_client.get_pods.assert_called_once()
    mock_logger.error.assert_any_call(
        "API call to get pods failed. Cannot perform cleanup actions."
    )
    mock_logger.error.assert_any_call(
        f"Failed to retrieve pods from RunPod API: {error_message}"
    )
    mock_api_client.stop_pod.assert_not_called()
    mock_api_client.terminate_pod.assert_not_called()
    assert result is False


# --- get_pod_counts() Tests ---

def test_get_pod_counts_no_pods(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test get_pod_counts returns zeros when no matching pods are found."""
    pod_lifecycle_manager.find_all_pods_by_name = MagicMock(return_value=[]) # Mock the dependency
    counts = pod_lifecycle_manager.get_pod_counts()
    pod_lifecycle_manager.find_all_pods_by_name.assert_called_once()
    assert counts == {"total": 0, "running": 0}


def test_get_pod_counts_one_running(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test get_pod_counts correctly counts one running pod."""
    pod_lifecycle_manager.find_all_pods_by_name = MagicMock(return_value=[RUNNING_POD])
    counts = pod_lifecycle_manager.get_pod_counts()
    pod_lifecycle_manager.find_all_pods_by_name.assert_called_once()
    assert counts == {"total": 1, "running": 1}


def test_get_pod_counts_one_stopped(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test get_pod_counts correctly counts one stopped pod."""
    pod_lifecycle_manager.find_all_pods_by_name = MagicMock(return_value=[STOPPED_POD])
    counts = pod_lifecycle_manager.get_pod_counts()
    pod_lifecycle_manager.find_all_pods_by_name.assert_called_once()
    assert counts == {"total": 1, "running": 0}


def test_get_pod_counts_one_running_one_stopped(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock
):
    """Test get_pod_counts correctly counts a mix of running and stopped pods."""
    # Note: find_all_pods_by_name should only return matching pods
    pod_lifecycle_manager.find_all_pods_by_name = MagicMock(
        return_value=[RUNNING_POD, MATCHING_STOPPED_POD_2]
    )
    counts = pod_lifecycle_manager.get_pod_counts()
    pod_lifecycle_manager.find_all_pods_by_name.assert_called_once()
    assert counts == {"total": 2, "running": 1}


def test_get_pod_counts_api_failure(
    pod_lifecycle_manager: PodLifecycleManager, mock_api_client: MagicMock, mock_logger: MagicMock
):
    """Test get_pod_counts returns False when find_all_pods_by_name fails."""
    pod_lifecycle_manager.find_all_pods_by_name = MagicMock(return_value=None)

    counts = pod_lifecycle_manager.get_pod_counts()

    pod_lifecycle_manager.find_all_pods_by_name.assert_called_once()
    mock_logger.error.assert_called_once_with(
        "API call to get pods failed. Cannot determine pod counts."
    )
    assert counts is False
