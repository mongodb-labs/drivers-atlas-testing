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

from requests.auth import HTTPDigestAuth


ClientConfiguration = namedtuple(
    "AtlasClientConfiguration",
    ["base_url", "api_version", "auth", "timeout", "verbose"])


# Default configuration values.
_DEFAULT_HTTP_TIMEOUT = 10
_DEFAULT_API_VERSION = 1.0
_DEFAULT_BASE_URL = "https://cloud.mongodb.com/api/atlas"


def get_client_configuration(*, base_url, api_version, username,
                             password, timeout, verbose):
    if not username or not password:
        raise ValueError("Username and/or password cannot be empty.")

    config = ClientConfiguration(
        base_url=base_url or _DEFAULT_BASE_URL,
        api_version=api_version or _DEFAULT_API_VERSION,
        auth=HTTPDigestAuth(username=username,
                            password=password),
        timeout=timeout or _DEFAULT_HTTP_TIMEOUT,
        verbose=verbose)
    return config
