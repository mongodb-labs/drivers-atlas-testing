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

from atlasclient.utils import JSONObject

CONFIG_DEFAULTS = JSONObject.from_dict({
    "ORGANIZATION_NAME": "MongoDB",
    "DB_USERNAME": "atlasuser",
    "DB_PASSWORD": "mypassword123",
    "POLLING_TIMEOUT": 1200.0,
    "POLLING_FREQUENCY": 1.0,
    "LOG_VERBOSITY": "INFO"
})


CONFIG_ENVVARS = JSONObject.from_dict({
    "PROJECT_NAME": "ATLAS_PROJECT_NAME",         # ${project} in EVG
    "CLUSTER_NAME_SALT": "EVERGREEN_BUILD_ID",      # ${build_id} in EVG
    "POLLING_TIMEOUT": "ATLAS_POLLING_TIMEOUT",
    "POLLING_FREQUENCY": "ATLAS_POLLING_FREQUENCY",
    "BASE_URL": "ATLAS_API_BASE_URL",
    "API_USERNAME": "ATLAS_API_USERNAME",
    "API_PASSWORD": "ATLAS_API_PASSWORD",
    "HTTP_TIMEOUT": "ATLAS_HTTP_TIMEOUT",
    "LOG_VERBOSITY": "ASTROLABE_LOGLEVEL"
})


CLI_OPTION_NAMES = JSONObject.from_dict({
    "PROJECT_NAME": "--group-name",
    "CLUSTER_NAME_SALT": "--cluster-name-salt",
    "POLLING_TIMEOUT": "--polling-timeout",
    "POLLING_FREQUENCY": "--polling-frequency",
    "API_USERNAME": "--atlas-api-username",
    "API_PASSWORD": "--atlas-api-password",
    "DB_USERNAME" : "--db-username",
    "DB_PASSWORD" : "--db-password",
    "ORGANIZATION_NAME": "--org-name",
    "BASE_URL": "--atlas-base-url",
    "HTTP_TIMEOUT": "--http-timeout",
    "LOG_VERBOSITY": "--log-level"
})


# Convenience class for storing settings related to polling.
TestCaseConfiguration = namedtuple(
    "AtlasPlannedMaintenanceTestConfiguration",
    ["organization_name", "group_name", "name_salt", "polling_timeout",
     "polling_frequency", "database_username", "database_password",
     "workload_executor"])
