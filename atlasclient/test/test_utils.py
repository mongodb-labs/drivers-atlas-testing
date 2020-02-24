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

"""Tests for atlasclient.utils submodule."""

import unittest

from atlasclient.utils import JSONObject


class TestJSONDecoder(unittest.TestCase):
    def test_simple(self):
        json_data = {
            'foo': 1,
            'bar': 'hello world'}
        json_obj = JSONObject(json_data)

        for key, value in json_data.items():
            self.assertEqual(getattr(json_obj, key), json_data[key])
            self.assertEqual(getattr(json_obj, key), value)

    def test_nested(self):
        json_data = {
            'a': {'b': {1: 'foo'}}}
        json_obj = JSONObject(json_data)

        def _walk_nested_json_and_assert(jdata, jobj):
            for key, value in jdata.items():
                if isinstance(value, dict):
                    self.assertIsInstance(getattr(jobj, key), JSONObject)
                    self.assertEqual(getattr(jobj, key), value)
                    _walk_nested_json_and_assert(value, getattr(jobj, key))

        _walk_nested_json_and_assert(json_data, json_obj)
