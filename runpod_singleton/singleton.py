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


class RunpodSingletonManager:
    """
    Manages the lifecycle of a named RunPod pod instance.

    This class handles checking for existing pods, validating their state,
    starting stopped pods, terminating invalid pods, and creating new pods
    based on the provided configuration.
    """

    def __init__(
        self, config: dict[str, Any], api_key: str | None, debug: bool = False
    ):
        """
        Initializes the RunpodSingletonManager.

        :param config: Dictionary containing the pod configuration.
        :type config: Dict[str, Any]
        :param api_key: The RunPod API key.
        :type api_key: str | None
        :param debug: Flag to enable debug logging.
        :type debug: bool
        """
        self.config: dict[str, Any] = config
        self.set_api_key(api_key)
        self.debug: bool = debug
        self.pod_name: str = config[const.POD_NAME]
        self.log: logging.Logger = Logger(self.__class__.__name__, debug=self.debug)
        self.log.debug("RunpodSingletonManager initialized.")
        self.log.info(f"Target Pod Name: {self.pod_name}")

    def set_api_key(self, api_key: str | None) -> None:
        """
        Sets the RunPod API key.

        :param api_key: The RunPod API key.
        :type api_key: str | None
        """
        api_key = api_key or os.environ.get("RUNPOD_API_KEY")
        if not api_key:
            raise RuntimeError(
                "RunPod API key not provided via argument or RUNPOD_API_KEY environment variable."
            )
        runpod.api_key = api_key

    def _get_pod_by_name(self, pods: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        Finds a pod by name from a list of pods.

        :param pods: List of pod dictionaries from the RunPod API.
        :type pods: List[Dict[str, Any]]
        :return: The matching pod dictionary or None if not found.
        :rtype: Dict[str, Any] | None
        """
        self.log.info(
            f"Searching for pod with name '{self.pod_name}' in {len(pods)} pods."
        )
        for pod in pods:
            if pod.get(const.POD_NAME_API) == self.pod_name:
                self.log.debug(f"Found pod: {pod.get(const.POD_ID)}")
                return pod
        self.log.info(f"Pod with name '{self.pod_name}' not found.")
        return None

    def _create_pod(self, gpu_type_id: str) -> str | None:
        """
        Attempts to create a new pod with the specified GPU type.

        :param gpu_type_id: The GPU type ID to use for creation.
        :type gpu_type_id: str
        :return: The ID of the newly created pod if successful, None otherwise.
        :rtype: str | None
        """
        self.log.info(
            f"Attempting to create pod '{self.pod_name}' with GPU type '{gpu_type_id}'..."
        )
        try:
            response = runpod.create_pod(
                name=self.pod_name,
                image_name=self.config[const.IMAGE_NAME],
                gpu_type_id=gpu_type_id,
                cloud_type=self.config.get(const.CLOUD_TYPE, const.DEFAULT_CLOUD_TYPE),
                support_public_ip=self.config.get(
                    const.SUPPORT_PUBLIC_IP, const.DEFAULT_SUPPORT_PUBLIC_IP
                ),
                start_ssh=self.config.get(const.START_SSH, const.DEFAULT_START_SSH),
                data_center_id=self.config.get(const.DATA_CENTER_ID),
                country_code=self.config.get(const.COUNTRY_CODE),
                gpu_count=self.config.get(const.GPU_COUNT, const.DEFAULT_GPU_COUNT),
                volume_in_gb=self.config.get(
                    const.VOLUME_IN_GB, const.DEFAULT_VOLUME_IN_GB
                ),
                container_disk_in_gb=self.config.get(const.CONTAINER_DISK_IN_GB),
                min_vcpu_count=self.config.get(
                    const.MIN_VCPU_COUNT, const.DEFAULT_MIN_VCPU_COUNT
                ),
                min_memory_in_gb=self.config.get(
                    const.MIN_MEMORY_IN_GB, const.DEFAULT_MIN_MEMORY_IN_GB
                ),
                docker_args=self.config.get(
                    const.DOCKER_ARGS, const.DEFAULT_DOCKER_ARGS
                ),
                ports=self.config.get(const.PORTS),
                volume_mount_path=self.config.get(
                    const.VOLUME_MOUNT_PATH, const.DEFAULT_VOLUME_MOUNT_PATH
                ),
                env=self.config.get(const.ENV),
                template_id=self.config.get(const.TEMPLATE_ID),
                network_volume_id=self.config.get(const.NETWORK_VOLUME_ID),
                allowed_cuda_versions=self.config.get(const.ALLOWED_CUDA_VERSIONS),
                min_download=self.config.get(const.MIN_DOWNLOAD),
                min_upload=self.config.get(const.MIN_UPLOAD),
            )
            if self.debug:
                pprint.pprint(response)
            new_pod_id = response.get(const.POD_ID)
            if new_pod_id:
                self.log.info(
                    f"Pod creation initiated successfully. New Pod ID: {new_pod_id}"
                )
                return new_pod_id
            else:
                self.log.error(
                    f"Pod creation request failed or did not return an ID. Response: {response}"
                )
                return None
        except Exception as e:
            self.log.error(f"Error creating pod with GPU {gpu_type_id}: {e}")
            return None

    def _start_pod(self, pod_id: str) -> bool:
        """
        Attempts to start (resume) a stopped pod.

        :param pod_id: The ID of the pod to start.
        :type pod_id: str
        :return: True if the start command was successful, False otherwise.
        :rtype: bool
        """
        self.log.info(f"Attempting to start pod with ID '{pod_id}'...")
        try:
            # Runpod resume_pod doesn't return detailed success/failure in the same way as create
            # We assume success if no exception is raised, but will validate GPU attachment later.
            self.log.info(f"Resuming pod'{pod_id}'.")
            response = runpod.resume_pod(
                pod_id,
                gpu_count=self.config.get(const.GPU_COUNT, const.DEFAULT_GPU_COUNT),
            )
            if self.debug:
                pprint.pprint(response)
            self.log.debug(f"Pod resume command sent for pod ID '{pod_id}'.")
            return True
        except Exception as e:
            self.log.error(f"Error starting pod {pod_id}: {e}")
            return False

    def _terminate_pod(self, pod_id: str) -> None:
        """
        Terminates a pod.

        :param pod_id: The ID of the pod to terminate.
        :type pod_id: str
        """
        self.log.warning(f"Terminating pod with ID '{pod_id}'...")
        try:
            response = runpod.terminate_pod(pod_id)
            if self.debug:
                pprint.pprint(response)
            self.log.info(f"Pod {pod_id} terminated successfully.")
        except Exception as e:
            self.log.error(f"Error terminating pod {pod_id}: {e}")

    def _handle_existing_pod(self, pod: dict[str, Any]) -> bool:
        """
        Manages an existing pod based on its status and GPU attachment.

        :param pod: The dictionary representing the existing pod.
        :type pod: Dict[str, Any]
        :return: True if the pod is now in the desired state (running with GPUs), False otherwise.
        :rtype: bool
        """
        pod_id = pod[const.POD_ID]
        pod_status = pod.get(const.POD_STATUS)
        self.log.info(
            f"Pod '{self.pod_name}' (ID: {pod_id}) already exists with status: {pod_status}"
        )

        if pod_status == const.POD_STATUS_RUNNING:
            self.log.info("Pod is running, no action needed.")
            return True
        # Pod is stopped or in an intermediate state
        else:
            self.log.info(f"Pod status is '{pod_status}'. Attempting to start...")
            if self._start_pod(pod_id):
                try:
                    updated_pod_info = runpod.get_pod(pod_id)
                    if self.debug:
                        pprint.pprint(updated_pod_info)
                    if updated_pod_info.get(const.POD_STATUS) == const.POD_STATUS_RUNNING:
                        self.log.info("Pod started successfully with GPUs attached.")
                        return True
                    else:
                        self.log.warning(
                            "Pod started but is not running. Terminating..."
                        )
                        self._terminate_pod(pod_id)
                        return False
                except Exception as e:
                    self.log.error(
                        f"Failed to get updated pod info for {pod_id} after start attempt: {e}"
                    )
                    # Terminate if we can't verify state
                    self._terminate_pod(pod_id)
                    return False
            else:
                self.log.error(
                    "Failed to send start command for the pod. Terminating..."
                )
                # Terminate if starting failed
                self._terminate_pod(pod_id)
                return False

    def _attempt_new_pod_creation(self) -> bool:
        """
        Iterates through configured GPU types and attempts to create a new pod.

        :return: True if a pod was successfully created and validated, False otherwise.
        :rtype: bool
        """
        self.log.info("No suitable existing pod found. Attempting to create a new one.")
        retries = (
            self.config.get("create_gpu_retries") or const.DEFAULT_CREATE_GPU_RETRIES
        )
        wait = (
            self.config.get("create_retry_wait_seconds")
            or const.DEFAULT_CREATE_RETRY_WAIT_SECONDS
        )
        gpu_types: list[str] = self.config.get(const.GPU_TYPES, [])
        if not gpu_types:
            self.log.error(
                "No GPU types specified in configuration. Cannot create pod."
            )
            return False

        for gpu_type in gpu_types:
            for x in range(retries, retries + 1):
                self.log.info(
                    f"Attempting to create pod with GPU type '{gpu_type}' (attempt {x}/{retries})..."
                )
                new_pod_id = self._create_pod(gpu_type)
                if new_pod_id:
                    # Validate the newly created pod
                    try:
                        new_pod_details = runpod.get_pod(new_pod_id)
                        if self.debug:
                            pprint.pprint(new_pod_details)
                        if new_pod_details.get(const.POD_NAME_API) == self.pod_name:
                            self.log.info(
                                f"Pod '{self.pod_name}' created successfully with GPU type '{gpu_type}' and validated."
                            )
                            return True
                        else:
                            self.log.warning(
                                f"Pod {new_pod_id} created but failed validation (name mismatch or no GPUs). Terminating..."
                            )
                            self._terminate_pod(new_pod_id)
                    except Exception as e:
                        self.log.error(
                            f"Error validating newly created pod {new_pod_id}: {e}. Terminating..."
                        )
                        self._terminate_pod(new_pod_id)
                else:
                    self.log.warning(
                        f"Failed to initiate pod creation with GPU type '{gpu_type}'. Trying next type in {wait} seconds..."
                    )
                    time.sleep(wait)

        self.log.error("All GPU options exhausted. Failed to create a persistent pod.")
        return False

    def manage(self) -> bool:
        """
        Executes the main logic to manage the persistent pod.

        Checks for an existing pod, handles it, or attempts to create a new one.

        :return: True if a pod is successfully running with GPUs, False otherwise.
        :rtype: bool
        """
        self.log.info("Starting persistent pod management...")
        try:
            pods = runpod.get_pods()
            self.log.debug(f"Retrieved {len(pods)} pods from RunPod API.")
        except Exception as e:
            self.log.critical(f"Failed to retrieve pods from RunPod API: {e}")
            return False
        existing_pod = self._get_pod_by_name(pods)
        if existing_pod:
            if self._handle_existing_pod(existing_pod):
                return True
            else:
                self.log.info(
                    "Existing pod was terminated or invalid. Proceeding to create a new pod."
                )
        return self._attempt_new_pod_creation()


def main() -> None:
    """
    Main entry point for the script. Parses arguments, loads config,
    and runs the pod management logic.
    """
    parser = argparse.ArgumentParser(
        description="Manage a persistent RunPod singleton instance."
    )
    parser.add_argument(
        "config", type=Path, help="Path to the YAML configuration file."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="RunPod API key (can also be set via RUNPOD_API_KEY environment variable).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(const.EXIT_FAILURE)

    manager = RunpodSingletonManager(
        config=config, api_key=args.api_key, debug=args.debug
    )

    try:
        success = manager.manage()
        if success:
            manager.log.info("Pod management completed successfully.")
            sys.exit(const.EXIT_SUCCESS)
        else:
            manager.log.error("Pod management failed.")
            sys.exit(const.EXIT_FAILURE)
    except Exception as e:
        manager.log.critical(
            f"An unexpected error occurred during pod management: {e}",
            exc_info=args.debug,
        )
        sys.exit(const.EXIT_FAILURE)


if __name__ == "__main__":
    main()
