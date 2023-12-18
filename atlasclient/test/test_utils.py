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
        json_data = {"foo": 1, "bar": "hello world"}

        # Test both __init__ and from_dict constructors.
        for mapping_obj in (JSONObject(json_data), JSONObject.from_dict(json_data)):
            for key, value in mapping_obj.items():
                self.assertEqual(getattr(mapping_obj, key), json_data[key])
                self.assertEqual(getattr(mapping_obj, key), value)

    def test_error(self):
        json_obj = JSONObject.from_dict({})
        with self.assertRaises(AttributeError):
            json_obj.a

    def test_nested(self):
        json_data = {"a": {"b": {"c": 1}}}

        # Using __init__ only enables dot-access of top level fields.
        json_obj = JSONObject(json_data)
        with self.assertRaises(AttributeError):
            self.assertEqual(json_obj.a.b.c, 1)

        # Using from_dict enables dot-access at all nesting levels.
        json_obj = JSONObject.from_dict(json_data)
        self.assertEqual(json_obj.a.b, {"c": 1})
        self.assertEqual(json_obj.a.b.c, 1)
