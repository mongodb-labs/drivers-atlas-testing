# Copyright 2020-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import namedtuple

import click

from atlasclient.configuration import CONFIG_DEFAULTS as CL_DEFAULTS
from atlasclient.utils import JSONObject


# Mapping used to generate configurable options for Astrolabe.
# See astrolabe.utils.create_click_option for details.
CONFIGURATION_OPTIONS = JSONObject(
    {
        "ATLAS_PROJECT_BASE_NAME": {  # ${project} in EVG
            "help": "Base of the Atlas Project.",
            "cliopt": "--project-base-name",
            "envvar": "ATLAS_PROJECT_BASE_NAME",
        },
        "ATLAS_PROJECT_NAME": {  # ${project}-timestamp-random_id in EVG
            "help": "Name of the Atlas Project.",
            "cliopt": "--project-name",
            "envvar": "ATLAS_PROJECT_NAME",
        },
        "CLUSTER_NAME_SALT": {  # ${build_id} in EVG
            "help": "Salt for generating unique hashes.",
            "cliopt": "--cluster-name-salt",
            "envvar": "CLUSTER_NAME_SALT",
        },
        "ATLAS_POLLING_TIMEOUT": {
            "type": click.FLOAT,
            "help": "Maximum time (in s) to poll API endpoints.",
            "cliopt": "--polling-timeout",
            "envvar": "ATLAS_POLLING_TIMEOUT",
            "default": 3600.0,
        },
        "ATLAS_POLLING_FREQUENCY": {
            "type": click.FLOAT,
            "help": "Frequency (in Hz) at which to poll API endpoints.",
            "cliopt": "--polling-frequency",
            "envvar": "ATLAS_POLLING_FREQUENCY",
            "default": 1.0,
        },
        "ATLAS_API_USERNAME": {
            "help": "HTTP-Digest username (Atlas API public-key).",
            "cliopt": "--atlas-api-username",
            "envvar": "ATLAS_API_USERNAME",
            "default": None,
        },
        "ATLAS_API_PASSWORD": {
            "help": "HTTP-Digest password (Atlas API private-key).",
            "cliopt": "--atlas-api-password",
            "envvar": "ATLAS_API_PASSWORD",
            "default": None,
        },
        "ATLAS_ADMIN_API_USERNAME": {
            "help": "HTTP-Digest username (Atlas API public-key).",
            "cliopt": "--atlas-admin-api-username",
            "envvar": "ATLAS_ADMIN_API_USERNAME",
            "default": None,
        },
        "ATLAS_ADMIN_API_PASSWORD": {
            "help": "HTTP-Digest password (Atlas API private-key).",
            "cliopt": "--atlas-admin-api-password",
            "envvar": "ATLAS_ADMIN_API_PASSWORD",
            "default": None,
        },
        "ATLAS_DB_USERNAME": {
            "help": "Database username on the MongoDB instance.",
            "cliopt": "--db-username",
            "default": "atlasuser",
        },
        "ATLAS_DB_PASSWORD": {
            "help": "Database password on the MongoDB instance.",
            "cliopt": "--db-password",
            "default": "mypassword123",
        },
        "ATLAS_ORGANIZATION_NAME": {
            "help": "Name of the Atlas Organization.",
            "cliopt": "--org-name",
            "envvar": "ATLAS_ORGANIZATION_NAME",
            "default": "MongoDB Drivers Team",
        },
        "ATLAS_ORGANIZATION_ID": {
            "help": "ID of the Atlas Organization.",
            "cliopt": "--org-id",
            "envvar": "ATLAS_ORGANIZATION_ID",
            "default": None,
        },
        "ATLAS_API_BASE_URL": {
            "help": "Base URL of the Atlas API.",
            "cliopt": "--atlas-base-url",
            "envvar": "ATLAS_API_BASE_URL",
            "default": CL_DEFAULTS.ATLAS_API_BASE_URL,
        },
        "ATLAS_HTTP_TIMEOUT": {
            "type": click.FLOAT,
            "help": "Time (in s) after which HTTP requests should timeout.",
            "cliopt": "--http-timeout",
            "envvar": "ATLAS_HTTP_TIMEOUT",
            "default": CL_DEFAULTS.ATLAS_HTTP_TIMEOUT,
        },
        "ASTROLABE_LOGLEVEL": {
            "type": click.Choice(
                ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
            ),
            "help": "Set the logging level.",
            "cliopt": ("-v", "--log-level"),
            "envvar": "ASTROLABE_LOGLEVEL",
            "default": "INFO",
        },
        "ASTROLABE_EXECUTOR_STARTUP_TIME": {
            "type": click.FLOAT,
            "help": "Time (in s) to wait for the executor to start running.",
            "cliopt": "--startup-time",
            "envvar": "ASTROLABE_EXECUTOR_STARTUP_TIME",
            "default": 1.0,
        },
    }
)


# Convenience class for storing settings related to polling.
TestCaseConfiguration = namedtuple(
    "AtlasPlannedMaintenanceTestConfiguration",
    [
        "organization_name",
        "organization_id",
        "project_name",
        "project_base_name",
        "name_salt",
        "polling_timeout",
        "polling_frequency",
        "database_username",
        "database_password",
        "workload_executor",
    ],
)
