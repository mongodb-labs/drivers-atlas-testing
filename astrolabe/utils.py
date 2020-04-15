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

import logging
import os
import signal
import subprocess
import sys
import tempfile
from hashlib import sha256
from time import monotonic

import click
import junitparser

from pymongo import MongoClient


class ClickLogHandler(logging.Handler):
    """Handler for print log statements via Click's echo functionality."""
    def emit(self, record):
        try:
            msg = self.format(record)
            use_stderr = False
            if record.levelno >= logging.WARNING:
                use_stderr = True
            click.echo(msg, err=use_stderr)
        except Exception:
            self.handleError(record)


def assert_subset(dict1, dict2):
    """Utility that asserts that `dict2` is a subset of `dict1`, while
    accounting for nested fields."""
    for key, value in dict2.items():
        if key not in dict1:
            raise AssertionError("not a subset")
        if isinstance(value, dict):
            assert_subset(dict1[key], value)
        else:
            assert dict1[key] == value


class Timer:
    """Class to simplify timing operations."""
    def __init__(self):
        self._start = None
        self._end = None

    def reset(self):
        self.__init__()

    def start(self):
        self._start = monotonic()
        self._end = None

    def stop(self):
        self._end = monotonic()

    @property
    def elapsed(self):
        if self._end is None:
            return monotonic() - self._start
        return self._end - self._start


def encode_cdata(data):
    """Encode `data` to XML-recognized CDATA."""
    return "<![CDATA[{data}]]>".format(data=data)


class SingleTestXUnitLogger:
    def __init__(self, *, output_directory):
        self._output_directory = os.path.realpath(os.path.join(
            os.getcwd(), output_directory))

        # Ensure folder exists.
        try:
            os.mkdir(self._output_directory)
        except FileExistsError:
            pass

    def write_xml(self, test_case, filename):
        filename += '.xml'
        xml_path = os.path.join(self._output_directory, filename)

        # Remove existing file if applicable.
        try:
            os.unlink(xml_path)
        except FileNotFoundError:
            pass

        # use filename as suitename
        suite = junitparser.TestSuite(filename)
        suite.add_testcase(test_case)

        xml = junitparser.JUnitXml()
        xml.add_testsuite(suite)
        xml.write(xml_path)


def get_test_name_from_spec_file(full_path):
    """Generate test name from a spec test file."""
    _, filename = os.path.split(full_path)
    test_name = os.path.splitext(filename)[0].replace('-', '_')
    return test_name


def get_cluster_name(test_name, name_salt):
    """Generate unique cluster name from test name and salt."""
    name_hash = sha256(test_name.encode('utf-8'))
    name_hash.update(name_salt.encode('utf-8'))
    return name_hash.hexdigest()[:10]


def load_test_data(connection_string, driver_workload):
    """Insert the test data into the cluster."""
    kwargs = {'w': "majority"}
    try:
        import certifi
        kwargs['tlsCAFile'] = certifi.where()
    except ImportError:
        pass

    client = MongoClient(connection_string, **kwargs)
    coll = client.get_database(
        driver_workload.database).get_collection(
        driver_workload.collection)
    coll.drop()
    coll.insert(driver_workload.testData)


class DriverWorkloadSubprocessRunner:
    """Convenience wrapper to run a workload executor in a subprocess."""
    def __init__(self):
        self.is_windows = False
        if sys.platform in ("win32", "cygwin"):
            self.is_windows = True
        self.workload_subprocess = None
        self.stderr_file = tempfile.TemporaryFile()
        self.stdout_file = tempfile.TemporaryFile()

    @property
    def pid(self):
        return self.workload_subprocess.pid

    @property
    def returncode(self):
        return self.workload_subprocess.returncode

    def spawn(self, *, workload_executor, connection_string, driver_workload):
        if not self.is_windows:
            self.workload_subprocess = subprocess.Popen([
                workload_executor, connection_string, driver_workload],
                preexec_fn=os.setsid, stdout=self.stdout_file,
                stderr=self.stderr_file)
        else:
            self.workload_subprocess = subprocess.Popen([
                "C:/cygwin/bin/sh",
                workload_executor, connection_string, driver_workload],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=self.stdout_file, stderr=self.stderr_file)
        return self.workload_subprocess

    def terminate(self):
        if not self.is_windows:
            os.killpg(self.workload_subprocess.pid, signal.SIGINT)
        else:
            os.kill(self.workload_subprocess.pid, signal.CTRL_C_EVENT)
        self.workload_subprocess.wait(timeout=10)
        self.stdout_file.seek(0)
        self.stderr_file.seek(0)
        stdout, stderr = self.stdout_file.read(), self.stderr_file.read()
        self.stdout_file.close()
        self.stderr_file.close()
        return stdout, stderr
