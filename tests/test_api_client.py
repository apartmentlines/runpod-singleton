import pytest
from unittest.mock import patch, MagicMock

# Import the stub class (it will be defined in singleton.py later)
# We need to import it this way initially until the refactoring is complete
from runpod_singleton.singleton import RunpodApiClient


@pytest.fixture
def mock_runpod_lib():
    """Fixture to mock the runpod library."""
    with patch("runpod_singleton.singleton.runpod", autospec=True) as mock_lib:
        yield mock_lib


def test_api_client_init(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient initialization sets the API key."""
    api_key = "test_api_key"
    client = RunpodApiClient(api_key=api_key)
    assert mock_runpod_lib.api_key == api_key
    assert client.api_key == api_key


def test_api_client_get_pods(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient.get_pods calls runpod.get_pods."""
    api_key = "test_key"
    client = RunpodApiClient(api_key=api_key)
    expected_pods = [{"id": "pod1"}, {"id": "pod2"}]
    mock_runpod_lib.get_pods.return_value = expected_pods

    pods = client.get_pods()

    mock_runpod_lib.get_pods.assert_called_once()
    assert pods == expected_pods


def test_api_client_get_pod(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient.get_pod calls runpod.get_pod."""
    api_key = "test_key"
    client = RunpodApiClient(api_key=api_key)
    pod_id = "test_pod_id"
    expected_pod_details = {"id": pod_id, "name": "test_pod"}
    mock_runpod_lib.get_pod.return_value = expected_pod_details

    pod_details = client.get_pod(pod_id)

    mock_runpod_lib.get_pod.assert_called_once_with(pod_id)
    assert pod_details == expected_pod_details


def test_api_client_create_pod(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient.create_pod calls runpod.create_pod."""
    api_key = "test_key"
    client = RunpodApiClient(api_key=api_key)
    create_args = {"name": "new_pod", "image_name": "image", "gpu_type_id": "gpu_id"}
    expected_response = {"id": "new_pod_id", "status": "CREATING"}
    mock_runpod_lib.create_pod.return_value = expected_response

    response = client.create_pod(**create_args)

    mock_runpod_lib.create_pod.assert_called_once_with(**create_args)
    assert response == expected_response


def test_api_client_resume_pod(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient.resume_pod calls runpod.resume_pod."""
    api_key = "test_key"
    client = RunpodApiClient(api_key=api_key)
    pod_id = "test_pod_id"
    gpu_count = 2
    expected_response = {"id": pod_id, "status": "RUNNING"}
    mock_runpod_lib.resume_pod.return_value = expected_response

    response = client.resume_pod(pod_id, gpu_count)

    mock_runpod_lib.resume_pod.assert_called_once_with(pod_id, gpu_count=gpu_count)
    assert response == expected_response


def test_api_client_stop_pod(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient.stop_pod calls runpod.stop_pod."""
    api_key = "test_key"
    client = RunpodApiClient(api_key=api_key)
    pod_id = "test_pod_id"
    expected_response = {"id": pod_id, "status": "EXITED"}
    mock_runpod_lib.stop_pod.return_value = expected_response

    response = client.stop_pod(pod_id)

    mock_runpod_lib.stop_pod.assert_called_once_with(pod_id)
    assert response == expected_response


def test_api_client_terminate_pod(mock_runpod_lib: MagicMock):
    """Test RunpodApiClient.terminate_pod calls runpod.terminate_pod."""
    api_key = "test_key"
    client = RunpodApiClient(api_key=api_key)
    pod_id = "test_pod_id"
    expected_response = {"id": pod_id, "status": "TERMINATED"}
    mock_runpod_lib.terminate_pod.return_value = expected_response

    response = client.terminate_pod(pod_id)

    mock_runpod_lib.terminate_pod.assert_called_once_with(pod_id)
    assert response == expected_response
