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

"""Utilities for the Python client for the MongoDB Atlas API."""

import logging

from http.client import HTTPConnection


class JSONObject(dict):
    """Dictionary with dot-notation read access."""
    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError('{} has no property named {}}.'.format(
            self.__class__.__name__, name))


def enable_http_logging(loglevel):
    """Enables logging of all HTTP requests."""
    # Enable logging for HTTP Requests and Responses.
    HTTPConnection.debuglevel = loglevel

    # Python logging levels are 0, 10, 20, 30, 40, 50
    py_loglevel = loglevel * 10
    logging.basicConfig()
    logging.getLogger().setLevel(py_loglevel)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(py_loglevel)
    requests_log.propagate = True
