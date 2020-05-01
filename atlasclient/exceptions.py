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

"""Exceptions used by the Python client for the MongoDB Atlas API."""


class AtlasApiBaseError(Exception):
    """Base Exception class for all ``atlasclient`` errors."""
    def __init__(self, msg, resource_url=None, request_method=None,
                 status_code=None, error_code=None, headers=None):
        self._msg = msg
        self.request_method = request_method
        self.resource_url = resource_url
        self.status_code = status_code
        self.error_code = error_code
        self.headers = headers

    def __str__(self):
        if self.request_method and self.resource_url:
            if self.error_code:
                return '{} Error Code: {!r} ({} {})'.format(
                    self._msg, self.error_code, self.request_method,
                    self.resource_url)
            else:
                return '{} ({} {})'.format(
                    self._msg, self.request_method, self.resource_url)
        return self._msg


class AtlasClientError(AtlasApiBaseError):
    pass


class AtlasApiError(AtlasApiBaseError):
    def __init__(self, msg, response=None, request_method=None,
                 error_code=None):
        kwargs = {'request_method': request_method,
                  'error_code': error_code}

        # Parse remaining fields from response object.
        if response is not None:
            kwargs.update({'status_code': response.status_code,
                           'resource_url': response.url,
                           'headers': response.headers})

        super().__init__(msg, **kwargs)

        # Store complete response (or None).
        self.raw_response = response


class AtlasRateLimitError(AtlasApiError):
    pass


class AtlasAuthenticationError(AtlasApiError):
    pass
