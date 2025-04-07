#!/usr/bin/env python3
"""
Manages a single, persistent RunPod pod instance based on a configuration file.

Ensures that a pod with a specific name exists, is running, and has GPUs attached.
If the pod exists but is stopped, it attempts to start it.
If the pod exists but lacks GPUs, it terminates it.
If the pod doesn't exist, it attempts to create one using a prioritized list of GPU types.
"""

import os
import sys
import yaml
import time
import pprint
import runpod
import argparse
import logging
from pathlib import Path
from typing import Any

from pyaml_env import parse_config

from .logger import Logger
from . import constants as const


class RunpodApiClient:
    """
    Facade/Wrapper for runpod SDK interactions. Isolates the external dependency.
    """
    def __init__(self, api_key: str):
        """
        Initializes the API client and sets the RunPod API key.

        :param api_key: The RunPod API key.
        :type api_key: str
        """
        self.api_key: str = api_key
        runpod.api_key = self.api_key

    def get_pods(self) -> list[dict[str, Any]]:
        """
        Retrieves a list of all pods for the current user.

        :return: A list of pod dictionaries.
        :rtype: list[dict[str, Any]]
        """
        # NOTE: get_pods() has a bad return signature, thus the linter ignore below.
        return runpod.get_pods()  # pyright: ignore[reportReturnType]

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        """
        Retrieves details for a specific pod.

        :param pod_id: The ID of the pod to retrieve.
        :type pod_id: str
        :return: A dictionary containing pod details.
        :rtype: dict[str, Any]
        """
        return runpod.get_pod(pod_id)

    def create_pod(self, **kwargs: Any) -> dict[str, Any]:
        """
        Creates a new pod with the specified configuration.

        Accepts keyword arguments corresponding to the parameters of runpod.create_pod.

        :param kwargs: Pod configuration parameters.
        :return: A dictionary containing the response from the RunPod API.
        :rtype: dict[str, Any]
        """
        return runpod.create_pod(**kwargs)

    def resume_pod(self, pod_id: str, gpu_count: int = 1) -> dict[str, Any]:
        """
        Resumes a stopped pod.

        :param pod_id: The ID of the pod to resume.
        :type pod_id: str
        :param gpu_count: The number of GPUs to attach upon resuming.
        :type gpu_count: int
        :return: A dictionary containing the response from the RunPod API.
        :rtype: dict[str, Any]
        """
        return runpod.resume_pod(pod_id, gpu_count=gpu_count)

    def stop_pod(self, pod_id: str) -> dict[str, Any]:
        """
        Stops a running pod.

        :param pod_id: The ID of the pod to stop.
        :type pod_id: str
        :return: A dictionary containing the response from the RunPod API.
        :rtype: dict[str, Any]
        """
        return runpod.stop_pod(pod_id)

    def terminate_pod(self, pod_id: str) -> dict[str, Any]:
        """
        Terminates a pod.

        :param pod_id: The ID of the pod to terminate.
        :type pod_id: str
        :return: A dictionary containing the response from the RunPod API.
        :rtype: dict[str, Any]
        """
        # NOTE: terminate_pod() has a bad return signature, thus the linter ignore below.
        return runpod.terminate_pod(pod_id)  # pyright: ignore[reportReturnType]


class PodLifecycleManager:
    """
    Encapsulates the core logic for managing and cleaning up pods based on
    configuration and state. Uses RunpodApiClient for API interactions.
    """

    def __init__(
        self,
        client: RunpodApiClient,
        config: dict[str, Any],
        logger: logging.Logger,
        stop: bool,
        terminate: bool,
    ):
        """
        Initializes the PodLifecycleManager.

        :param client: An initialized RunpodApiClient instance.
        :type client: RunpodApiClient
        :param config: The loaded application configuration dictionary.
        :type config: dict[str, Any]
        :param logger: A configured logger instance.
        :type logger: logging.Logger
        :param stop: Flag indicating if stop actions should be performed.
        :type stop: bool
        :param terminate: Flag indicating if terminate actions should be performed.
        :type terminate: bool
        """
        self.client: RunpodApiClient = client
        self.config: dict[str, Any] = config
        self.log: logging.Logger = logger
        self.stop: bool = stop
        self.terminate: bool = terminate
        self.pod_name: str = config[const.POD_NAME]
        self.gpu_types: list[str] = config.get(const.GPU_TYPES, [])
        self.gpu_count: int = config.get(const.GPU_COUNT, const.DEFAULT_GPU_COUNT)
        self.create_retries: int = config.get("create_gpu_retries", const.DEFAULT_CREATE_GPU_RETRIES)
        self.create_wait: int = config.get("create_retry_wait_seconds", const.DEFAULT_CREATE_RETRY_WAIT_SECONDS)

    def manage(self) -> str | None:
        """
        Orchestrates the primary goal: ensure one named pod is running.

        Finds the first matching pod. If found, handles its state (starts if stopped,
        validates). If not found, attempts to create a new one.

        :return: The pod ID (str) if a pod is successfully running at the end, None otherwise.
        :rtype: str | None
        """
        self.log.info("Starting singleton pod management...")
        existing_pod_result = self.find_first_pod_by_name()

        if existing_pod_result is None:
            self.log.error("API call to list pods failed during search. Cannot manage pod state.")
            return None

        if existing_pod_result:
            pod_id = self._handle_existing_pod(existing_pod_result)
            if pod_id:
                self.log.info(f"Existing pod {pod_id} is running and valid.")
                return pod_id
            else:
                self.log.warning(
                    "Handling existing pod failed. Attempting to create a new one."
                )
        else:
            self.log.info(f"No existing pod found with name '{self.pod_name}'.")

        return self._attempt_new_pod_creation()

    def perform_cleanup_actions(self) -> bool | None:
        """
        Orchestrates stopping and/or terminating pods based on flags.

        Finds all pods matching the configured name. If the stop flag is set,
        stops any running pods found. If the terminate flag is set, terminates
        all pods found.

        :return: True if the process completed without internal errors, None otherwise.
                 Note: API call success/failure is logged within this method.
        :rtype: bool | None
        """
        self.log.info("Starting cleanup actions...")
        matching_pods = self.find_all_pods_by_name()

        # Check if the API call failed
        if matching_pods is None:
            self.log.error("API call to get pods failed. Cannot perform cleanup actions.")
            return None

        if not matching_pods:
            self.log.info("No pods found matching the name. No cleanup actions needed.")
            return True

        if self.stop:
            self.log.info(f"Processing stop action for pod name '{self.pod_name}'.")
            running_pods_to_stop = [
                pod
                for pod in matching_pods
                if pod.get(const.POD_STATUS) == const.POD_STATUS_RUNNING
            ]
            if running_pods_to_stop:
                self.log.info(
                    f"Found {len(running_pods_to_stop)} running pods to stop."
                )
                for pod in running_pods_to_stop:
                    pod_id = pod[const.POD_ID]
                    try:
                        self.log.info(f"Attempting to stop pod {pod_id}...")
                        response = self.client.stop_pod(pod_id)
                        if self.log.isEnabledFor(logging.DEBUG):
                            self.log.debug(f"Stop API response for {pod_id}:")
                            pprint.pprint(response)
                        self.log.info(f"Stop command sent for pod {pod_id}.")
                    except Exception as e:
                        self.log.error(f"Error stopping pod {pod_id}: {e}")
            else:
                self.log.info("No running pods found matching the name to stop.")

        if self.terminate:
            self.log.info(
                f"Processing terminate action for {len(matching_pods)} pods matching name '{self.pod_name}'."
            )
            for pod in matching_pods:
                pod_id = pod[const.POD_ID]
                try:
                    self.log.warning(f"Attempting to terminate pod {pod_id}...")
                    response = self.client.terminate_pod(pod_id)
                    if self.log.isEnabledFor(logging.DEBUG):
                        self.log.debug(f"Terminate API response for {pod_id}:")
                        pprint.pprint(response)
                    self.log.info(f"Terminate command sent for pod {pod_id}.")
                except Exception as e:
                    self.log.error(f"Error terminating pod {pod_id}: {e}")

        self.log.info("Cleanup actions processing finished.")
        return True

    def _get_all_pods_from_api(self) -> list[dict[str, Any]] | None:
        """
        Helper to call the API client to get all pods.

        :return: A list of pod dictionaries from the API, or None if the call fails.
        :rtype: list[dict[str, Any]] | None
        :raises Exception: If the API call fails.
        """
        self.log.debug("Retrieving all pods from RunPod API...")
        try:
            pods = self.client.get_pods()
            self.log.debug(f"Retrieved {len(pods)} pods.")
            if self.log.isEnabledFor(logging.DEBUG):
                 pprint.pprint(pods)
            return pods
        except Exception as e:
            self.log.error(f"Failed to retrieve pods from RunPod API: {e}")
            return None

    def find_first_pod_by_name(self) -> dict[str, Any] | None:
        """
        Finds the first pod matching the configured name.

        :return: The first matching pod dictionary, an empty dictionary `{}` if none found,
                 or None if the API call failed.
        :rtype: dict[str, Any] | None
        """
        self.log.debug(f"Searching for first pod matching name '{self.pod_name}'...")
        all_pods = self._get_all_pods_from_api()

        if all_pods is None:
            self.log.error("API call to get pods failed. Cannot search for pod.")
            return None

        for pod in all_pods:
            if pod.get(const.POD_NAME_API) == self.pod_name:
                self.log.debug(f"Found first matching pod: ID {pod.get(const.POD_ID)}")
                if self.log.isEnabledFor(logging.DEBUG):
                    pprint.pprint(pod)
                return pod

        self.log.info(f"No pod found matching name '{self.pod_name}'.")
        return {}

    def find_all_pods_by_name(self) -> list[dict[str, Any]] | None:
        """
        Finds all pods matching the configured name.

        :return: A list of all matching pod dictionaries, or None if the API call fails.
        :rtype: list[dict[str, Any]] | None
        """
        self.log.debug(f"Searching for all pods matching name '{self.pod_name}'...")
        all_pods = self._get_all_pods_from_api()

        if all_pods is None:
            self.log.error("API call to get pods failed. Cannot find matching pods.")
            return None

        matching_pods = [
            pod for pod in all_pods if pod.get(const.POD_NAME_API) == self.pod_name
        ]
        self.log.info(f"Found {len(matching_pods)} pods matching name '{self.pod_name}'.")
        if self.log.isEnabledFor(logging.DEBUG) and matching_pods:
            self.log.debug(f"Matching pod IDs: {[p.get(const.POD_ID) for p in matching_pods]}")
            pprint.pprint(matching_pods)
        return matching_pods

    def _attempt_resume_pod(self, pod_id: str) -> bool:
        """
        Attempts to resume a specific pod.

        :param pod_id: The ID of the pod to resume.
        :type pod_id: str
        :return: True if the resume API call was initiated successfully, False otherwise.
        :rtype: bool
        """
        self.log.info(f"Attempting to resume pod {pod_id}...")
        try:
            resume_response = self.client.resume_pod(pod_id, gpu_count=self.gpu_count)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug(f"Resume API response for {pod_id}:")
                pprint.pprint(resume_response)
            self.log.debug(f"Resume command sent for pod {pod_id}.")
            return True
        except Exception as e:
            self.log.error(f"API error resuming pod {pod_id}: {e}")
            return False

    def _validate_resumed_pod(self, pod_id: str) -> bool:
        """
        Validates if a pod has reached the RUNNING state after a resume attempt.

        :param pod_id: The ID of the pod to validate.
        :type pod_id: str
        :return: True if the pod is RUNNING, False otherwise.
        :rtype: bool
        """
        self.log.info(f"Validating status of pod {pod_id} after resume attempt...")
        try:
            updated_pod_info = self.client.get_pod(pod_id)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug(f"Updated pod info for {pod_id}:")
                pprint.pprint(updated_pod_info)
            if updated_pod_info.get(const.POD_STATUS) == const.POD_STATUS_RUNNING:
                self.log.info(f"Pod {pod_id} resumed successfully and is RUNNING.")
                return True
            else:
                self.log.warning(
                    f"Pod {pod_id} did not reach RUNNING status after resume attempt (current status: {updated_pod_info.get(const.POD_STATUS)})."
                )
                return False
        except Exception as e:
            self.log.error(f"API error validating pod {pod_id} after resume: {e}")
            return False

    def _handle_existing_pod(self, pod: dict[str, Any]) -> str | None:
        """
        Manages an existing pod based on its status.

        :param pod: The dictionary representing the existing pod.
        :type pod: dict[str, Any]
        :return: The pod ID if the pod is running and valid after handling, None otherwise.
        :rtype: str | None
        """
        pod_id: str = pod[const.POD_ID]
        pod_status = pod.get(const.POD_STATUS)
        self.log.info(
            f"Handling existing pod '{self.pod_name}' (ID: {pod_id}) with status: {pod_status}"
        )

        if pod_status == const.POD_STATUS_RUNNING:
            self.log.info(f"Pod {pod_id} is already running.")
            return pod_id

        if self._attempt_resume_pod(pod_id):
            if self._validate_resumed_pod(pod_id):
                return pod_id
            else:
                self.log.warning(f"Validation failed after resuming pod {pod_id}. Terminating...")
                self._terminate_pod_silently(pod_id)
                return None
        else:
            self.log.warning(f"Resume attempt failed for pod {pod_id}. Terminating...")
            self._terminate_pod_silently(pod_id)
            return None

    def _attempt_new_pod_creation(self) -> str | None:
        """
        Attempts to create a new pod, iterating through configured GPU types.

        :return: The ID of the successfully created and validated pod, or None otherwise.
        :rtype: str | None
        """
        self.log.info("Attempting to create a new pod.")
        if not self.gpu_types:
            self.log.error("No GPU types specified in configuration. Cannot create pod.")
            return None

        for gpu_type in self.gpu_types:
            for attempt in range(1, self.create_retries + 1):
                self.log.info(
                    f"Processing GPU type '{gpu_type}' (attempt {attempt}/{self.create_retries})..."
                )
                pod_id = self._create_and_validate_pod_with_gpu(gpu_type)
                if pod_id:
                    return pod_id
                self.log.warning(
                    f"Create/validate attempt {attempt} failed for GPU type '{gpu_type}'."
                )
                if attempt < self.create_retries:
                    self.log.info(f"Waiting {self.create_wait} seconds before next attempt for '{gpu_type}'...")
                    time.sleep(self.create_wait)
                else:
                    self.log.warning(f"All {self.create_retries} attempts failed for GPU type '{gpu_type}'.")
        self.log.error(
            f"All creation attempts failed for all specified GPU types: {self.gpu_types}."
        )
        return None

    def _create_and_validate_pod_with_gpu(self, gpu_type: str) -> str | None:
        """
        Attempts to create a pod with a specific GPU type and validates it.

        :param gpu_type: The GPU type ID to use for this attempt.
        :type gpu_type: str
        :return: The pod ID if creation and validation are successful, None otherwise.
        :rtype: str | None
        """
        self.log.info(f"Attempting to create and validate pod with GPU type '{gpu_type}'...")
        new_pod_id = self._create_pod_attempt(gpu_type)
        if type(new_pod_id) is str:
            if self._validate_new_pod(new_pod_id):
                self.log.info(
                    f"Pod '{self.pod_name}' (ID: {new_pod_id}) created and validated successfully with GPU '{gpu_type}'."
                )
                return new_pod_id
            else:
                self.log.warning(
                    f"Validation failed for newly created pod {new_pod_id} with GPU '{gpu_type}'. Pod has been terminated."
                )
                return None
        else:
            self.log.warning(f"Pod creation attempt failed for GPU type '{gpu_type}'.")
            return None

    def _create_pod_attempt(self, gpu_type_id: str) -> str | None:
        """
        Performs a single attempt to create a pod with a specific GPU type.

        :param gpu_type_id: The GPU type ID to use for this attempt.
        :type gpu_type_id: str
        :return: The new pod ID if the creation API call is successful and returns an ID, None otherwise.
        :rtype: str | None
        """
        self.log.debug(f"Initiating create_pod API call for GPU type '{gpu_type_id}'.")
        create_params = {
            "name": self.pod_name,
            "image_name": self.config[const.IMAGE_NAME],
            "gpu_type_id": gpu_type_id,
            "gpu_count": self.gpu_count,
            "container_disk_in_gb": self.config[const.CONTAINER_DISK_IN_GB],
            "cloud_type": self.config.get(const.CLOUD_TYPE, const.DEFAULT_CLOUD_TYPE),
            "support_public_ip": self.config.get(const.SUPPORT_PUBLIC_IP, const.DEFAULT_SUPPORT_PUBLIC_IP),
            "start_ssh": self.config.get(const.START_SSH, const.DEFAULT_START_SSH),
            "volume_in_gb": self.config.get(const.VOLUME_IN_GB, const.DEFAULT_VOLUME_IN_GB),
            "min_vcpu_count": self.config.get(const.MIN_VCPU_COUNT, const.DEFAULT_MIN_VCPU_COUNT),
            "min_memory_in_gb": self.config.get(const.MIN_MEMORY_IN_GB, const.DEFAULT_MIN_MEMORY_IN_GB),
            "docker_args": self.config.get(const.DOCKER_ARGS, const.DEFAULT_DOCKER_ARGS),
            "volume_mount_path": self.config.get(const.VOLUME_MOUNT_PATH, const.DEFAULT_VOLUME_MOUNT_PATH),
            # Optional parameters - only include if present in config
            **{k: v for k, v in {
                const.DATA_CENTER_ID: self.config.get(const.DATA_CENTER_ID),
                const.COUNTRY_CODE: self.config.get(const.COUNTRY_CODE),
                const.PORTS: self.config.get(const.PORTS),
                const.ENV: self.config.get(const.ENV),
                const.TEMPLATE_ID: self.config.get(const.TEMPLATE_ID),
                const.NETWORK_VOLUME_ID: self.config.get(const.NETWORK_VOLUME_ID),
                const.ALLOWED_CUDA_VERSIONS: self.config.get(const.ALLOWED_CUDA_VERSIONS),
                const.MIN_DOWNLOAD: self.config.get(const.MIN_DOWNLOAD),
                const.MIN_UPLOAD: self.config.get(const.MIN_UPLOAD),
            }.items() if v is not None}
        }
        if self.log.isEnabledFor(logging.DEBUG):
            self.log.debug("Create pod parameters:")
            pprint.pprint(create_params)

        try:
            response = self.client.create_pod(**create_params)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug("Create pod API response:")
                pprint.pprint(response)

            new_pod_id = response.get(const.POD_ID)
            if new_pod_id:
                self.log.info(f"Pod creation initiated via API. New Pod ID: {new_pod_id}")
                return new_pod_id
            else:
                self.log.error(
                    f"Pod creation API call succeeded but did not return an ID. Response: {response}"
                )
                return None
        except Exception as e:
            self.log.error(f"API error creating pod with GPU {gpu_type_id}: {e}")
            return None

    def _validate_new_pod(self, pod_id: str) -> bool:
        """
        Validates a newly created pod.

        :param pod_id: The ID of the pod to validate.
        :type pod_id: str
        Calls client.get_pod() and checks if the pod details (name, status)
        match the expected state after creation. Terminates the pod if validation fails.

        :param pod_id: The ID of the pod to validate.
        :type pod_id: str
        :return: True if the pod is valid, False otherwise.
        :rtype: bool
        """
        self.log.info(f"Validating newly created pod {pod_id}...")
        try:
            pod_details = self.client.get_pod(pod_id)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug(f"Pod details for validation ({pod_id}):")
                pprint.pprint(pod_details)

            pod_name_matches = pod_details.get(const.POD_NAME_API) == self.pod_name
            pod_is_running = pod_details.get(const.POD_STATUS) == const.POD_STATUS_RUNNING

            if pod_name_matches and pod_is_running:
                self.log.info(f"Pod {pod_id} validation successful.")
                return True
            else:
                self.log.warning(
                    f"Pod {pod_id} validation failed. Name matches: {pod_name_matches} (Expected: '{self.pod_name}', Got: '{pod_details.get(const.POD_NAME_API)}'). Is running: {pod_is_running} (Status: '{pod_details.get(const.POD_STATUS)}'). Terminating pod..."
                )
                self._terminate_pod_silently(pod_id)
                return False
        except Exception as e:
            self.log.error(f"Error during validation of pod {pod_id}: {e}")
            self.log.warning(f"Terminating pod {pod_id} due to validation error.")
            self._terminate_pod_silently(pod_id)
            return False

    def _terminate_pod_silently(self, pod_id: str) -> None:
        """
        Terminates a pod and logs errors, but does not raise exceptions.

        :param pod_id: The ID of the pod to terminate.
        :type pod_id: str
        """
        try:
            self.log.warning(f"Terminating pod {pod_id} silently...")
            self.client.terminate_pod(pod_id)
            self.log.info(f"Terminate command sent for pod {pod_id}.")
        except Exception as e:
            self.log.error(f"Failed to terminate pod {pod_id} silently: {e}")

    def get_pod_counts(self) -> dict[str, int] | None:
        """
        Counts the total number of pods matching the configured name and how many are running.

        :return: A dictionary with 'total' and 'running' pod counts, or None if API fails.
        :rtype: dict[str, int] | None
        """
        self.log.debug(f"Getting counts for pods matching name '{self.pod_name}'...")
        matching_pods = self.find_all_pods_by_name()

        # Check if the API call failed
        if matching_pods is None:
            self.log.error("API call to get pods failed. Cannot determine pod counts.")
            return None

        total_count = len(matching_pods)
        running_count = sum(
            1
            for pod in matching_pods
            if pod.get(const.POD_STATUS) == const.POD_STATUS_RUNNING
        )
        self.log.debug(f"Pod counts: Total={total_count}, Running={running_count}")
        return {"total": total_count, "running": running_count}


class RunpodSingletonManager:
    """
    Orchestrates the setup process and delegates execution to PodLifecycleManager.
    Serves as the primary class for programmatic use and command-line entry.
    """

    def __init__(
        self,
        config_path: Path,
        api_key: str | None = None,
        stop: bool = False,
        terminate: bool = False,
        debug: bool = False,
    ):
        """
        Initializes the RunpodSingletonManager.

        Loads configuration, sets up logging, initializes the API client,
        and prepares for execution.

        :param config_path: Path to the YAML configuration file.
        :type config_path: Path
        :param api_key: The RunPod API key (optional, falls back to env var).
        :type api_key: str | None
        :param stop: Flag indicating if stop actions should be performed.
        :type stop: bool
        :param terminate: Flag indicating if terminate actions should be performed.
        :type terminate: bool
        :param debug: Flag to enable debug logging.
        :type debug: bool
        :raises FileNotFoundError: If the config file is not found.
        :raises yaml.YAMLError: If the config file is invalid.
        :raises RuntimeError: If the API key cannot be found.
        """
        self.config_path: Path = config_path
        self.stop: bool = stop
        self.terminate: bool = terminate
        self.debug: bool = debug
        self.log: logging.Logger = Logger(self.__class__.__name__, debug=self.debug)

        self.log.debug(f"Loading configuration from: {self.config_path}")
        self.config: dict[str, Any] = load_config(self.config_path)
        self.log.debug("Configuration loaded successfully.")

        self.client: RunpodApiClient = self._setup_api_client(api_key)
        self.log.info("RunpodSingletonManager initialized.")

    def _setup_api_client(self, api_key: str | None) -> RunpodApiClient:
        """
        Retrieves the API key and initializes the RunpodApiClient.

        Prioritizes the provided api_key argument, then the RUNPOD_API_KEY
        environment variable.

        :param api_key: API key passed during initialization (optional).
        :type api_key: str | None
        :return: An initialized RunpodApiClient instance.
        :rtype: RunpodApiClient
        :raises RuntimeError: If no API key is found.
        """
        self.log.debug("Setting up RunPod API client...")
        found_api_key = api_key or os.environ.get("RUNPOD_API_KEY")
        if not found_api_key:
            self.log.error("RunPod API key not found in arguments or environment variables.")
            raise RuntimeError(
                "RunPod API key not found. Provide it via --api-key or set RUNPOD_API_KEY environment variable."
            )
        self.log.debug("API key found. Initializing client.")
        return RunpodApiClient(api_key=found_api_key)

    def count_pods(self) -> dict[str, int] | None:
        """
        Retrieves the total and running counts for pods matching the configuration name.

        :return: A dictionary containing 'total' and 'running' counts, or None on failure.
        :rtype: dict[str, int] | None
        """
        self.log.info("Retrieving pod counts...")
        manager = PodLifecycleManager(
            self.client, self.config, self.log, stop=False, terminate=False
        )
        counts = manager.get_pod_counts()
        return counts

    def run(self) -> str | bool | None:
        """
        Executes the main logic: either cleanup actions or pod management.

        :return: For manage mode: The pod ID (str) on success, None on failure.
                 For cleanup mode: None on internal failure, True otherwise.
        :rtype: str | bool | None
        """
        self.log.debug("RunpodSingletonManager run() started.")
        result: str | bool | None = None
        try:
            manager = PodLifecycleManager(
                self.client, self.config, self.log, self.stop, self.terminate
            )
            if self.stop or self.terminate:
                self.log.info("Executing cleanup actions...")
                result = manager.perform_cleanup_actions()
                self.log.info(f"Cleanup actions completed with result: {result}")
            else:
                self.log.info("Executing pod management...")
                result = manager.manage()
                if result is None:
                    self.log.warning("Pod management failed.")
                else:
                    self.log.info(f"Pod management successful. Pod ID: {result}")
            return result
        except Exception as e:
            self.log.error(
                f"An unexpected error occurred during execution: {e}", exc_info=self.debug
            )
            return None


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    :return: Parsed arguments.
    :rtype: Namespace
    """
    parser = argparse.ArgumentParser(
        description="Manage or count a persistent RunPod singleton instance.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "config", type=Path, help="Path to the YAML configuration file."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="RunPod API key (can also be set via RUNPOD_API_KEY environment variable).",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Count total and running pods matching the configured name and exit.",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all running pods matching the configured name and exit (can be combined with --terminate).",
    )
    parser.add_argument(
        "--terminate",
        action="store_true",
        help="Terminate all pods matching the configured name and exit (can be combined with --stop).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging."
    )
    args = parser.parse_args()
    if args.count and (args.stop or args.terminate):
        parser.error("argument --count: not allowed with arguments --stop or --terminate")

    return args


def load_config(config_path: Path) -> dict[str, Any]:
    """
    Loads the YAML configuration file.

    :param config_path: Path to the configuration file.
    :type config_path: Path
    :return: Dictionary containing the configuration.
    :rtype: Dict[str, Any]
    :raises FileNotFoundError: If the config file does not exist.
    :raises yaml.YAMLError: If the config file is invalid YAML.
    """
    try:
        return parse_config(config_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file '{config_path}' not found.")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in config file '{config_path}': {e}")


def main() -> None:
    """
    Main entry point for the script. Parses arguments, instantiates the manager,
    runs the core logic, and handles final exit codes and top-level exceptions.
    """
    exit_code = const.EXIT_FAILURE
    args = parse_args()
    try:
        manager = RunpodSingletonManager(
            args.config, args.api_key, args.stop, args.terminate, args.debug
        )
        if args.count:
            counts = manager.count_pods()
            if counts is None:
                exit_code = const.EXIT_FAILURE
            else:
                pod_name = manager.config.get(const.POD_NAME, "N/A")
                print(f"Pods matching name '{pod_name}': Total={counts['total']}, Running={counts['running']}")
                exit_code = const.EXIT_SUCCESS
        else:
            success = manager.run()
            exit_code = const.EXIT_SUCCESS if success else const.EXIT_FAILURE
    except KeyboardInterrupt:
        print("\nOperation interrupted by user (Ctrl+C). Exiting.", file=sys.stderr)
        exit_code = const.EXIT_INTERRUPTED
    except Exception as e:
        print(f"\nCritical error during script execution: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc(file=sys.stderr)
        exit_code = const.EXIT_FAILURE
    finally:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
