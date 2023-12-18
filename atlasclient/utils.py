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

import json


class JSONObject(dict):
    """Dictionary object with dot-notation read access."""

    def __getattr__(self, name):
        if name in self:
            return self[name]
        raise AttributeError("{} has no property named {}.".format(self, name))

    @classmethod
    def from_dict(cls, raw_dict):
        """
        Create a JSONObject instance from the given dictionary.

        Using this constructor is the recommended way to create JSONObject
        instances from nested dictionaries as it guarantees the conversion
        of all nested dicts into JSONObjects. This ensures that
        dot-notation access works for keys at all nesting levels.
        """
        return json.loads(json.dumps(raw_dict), object_hook=JSONObject)
