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

"""Configuration options for the Python client for the MongoDB Atlas API."""

from collections import namedtuple

from atlasclient.utils import JSONObject


ClientConfiguration = namedtuple(
    "AtlasClientConfiguration",
    ["base_url", "api_version", "auth", "timeout"])


# Default configuration values.
CONFIG_DEFAULTS = JSONObject.from_dict({
    "ATLAS_HTTP_TIMEOUT": 10.0,
    "ATLAS_API_VERSION": 1.0,
    "ATLAS_API_BASE_URL": "https://cloud.mongodb.com/api/atlas"})
