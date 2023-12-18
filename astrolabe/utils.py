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

import datetime
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
from contextlib import closing
from hashlib import sha256
from time import sleep

import click
import junitparser
import requests.packages.urllib3.util.connection as urllib3_cn
from pymongo import MongoClient

from .exceptions import (
    AstrolabeTestCaseError,
    PrematureExitError,
    WorkloadExecutorError,
)
from .poller import poll

LOGGER = logging.getLogger(__name__)


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


def create_click_option(option_spec, **kwargs):
    """Utility that creates a click option decorator from an `option_spec`
    mapping. Optionally, the user can pass `**kwargs` which are passed
    directly to the click.option constructor. The `option_spec` mapping
    has the following keys:

      - help (required): help-text for this option
      - cliopt (required): command-line parameter name for this option; can
        be a tuple to specify short and long-form names for an option
      - envvar (optional): environment variable name for this option; option
        values cannot be specified using an environment variable by default
      - type (optional): click type to use for validating the user-input value
        for this option; defaults to click.STRING
      - default (optional): default value for this option; if provided, this
        will be displayed in the help text unless `show_default=False` is
        passed in the `**kwargs`; if not provided, the option will be
        assumed to be `required=True`
    """
    click_kwargs = {
        "type": option_spec.get("type", click.STRING),
        "help": option_spec["help"],
    }
    if "envvar" in option_spec:
        kwargs["envvar"] = option_spec["envvar"]
    if "default" in option_spec:
        kwargs["default"] = option_spec["default"]
        kwargs["show_default"] = True
    else:
        kwargs["required"] = True

    click_kwargs.update(kwargs)
    if isinstance(option_spec["cliopt"], tuple):
        return click.option(*option_spec["cliopt"], **click_kwargs)
    return click.option(option_spec["cliopt"], **click_kwargs)


def assert_subset(dict1, dict2):
    """Utility that asserts that `dict2` is a subset of `dict1`, while
    accounting for nested fields."""
    for key, value2 in dict2.items():
        if key not in dict1:
            raise AssertionError(
                "not a subset: '%s' from %s is not in %s"
                % (key, repr(dict2), repr(dict1))
            )
        value1 = dict1[key]
        if isinstance(value2, dict):
            assert_subset(value1, value2)
        elif isinstance(value2, list):
            assert len(value1) == len(value2)
            for i in range(len(value2)):
                if isinstance(value2[i], dict):
                    assert_subset(value1[i], value2[i])
                else:
                    assert value1[i] == value2[i]
        else:
            assert value1 == value2, (
                "Different values for '%s':\nexpected '%s'\nactual   '%s'"
                % (key, repr(dict2[key]), repr(dict1[key]))
            )


class SingleTestXUnitLogger:
    def __init__(self, *, output_directory):
        self._output_directory = os.path.realpath(
            os.path.join(os.getcwd(), output_directory)
        )

        # Ensure folder exists.
        try:
            os.mkdir(self._output_directory)
        except FileExistsError:
            pass

    def write_xml(self, test_case, filename):
        filename += ".xml"
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


def get_test_name(spec_test_file, workload_file):
    """
    Generate test name from a spec test file and workload file.

    The test name is "{spec test filename}-{workload filename}".
    """
    return f"{os.path.basename(spec_test_file)}-{os.path.basename(workload_file)}"


def get_cluster_name(test_name, name_salt):
    """Generate unique cluster name from test name and salt."""
    name_hash = sha256(test_name.encode("utf-8"))
    name_hash.update(name_salt.encode("utf-8"))
    return name_hash.hexdigest()[:10]


def mongo_client(connection_string):
    kwargs = {"w": "majority"}

    # TODO: remove this if...else block after BUILD-10841 is done.
    if sys.platform in ("win32", "cygwin") and connection_string.startswith(
        "mongodb+srv://"
    ):
        import certifi

        kwargs["tlsCAFile"] = certifi.where()
    client = MongoClient(connection_string, **kwargs)

    return closing(client)


class DriverWorkloadSubprocessRunner:
    """Convenience wrapper to run a workload executor in a subprocess."""

    def __init__(self):
        self.is_windows = False
        if sys.platform in ("win32", "cygwin"):
            self.is_windows = True
        self.workload_subprocess = None
        self.sentinel = os.path.join(os.path.abspath(os.curdir), "results.json")
        self.events = os.path.join(os.path.abspath(os.curdir), "events.json")

    @property
    def pid(self):
        return self.workload_subprocess.pid

    @property
    def returncode(self):
        return self.workload_subprocess.returncode

    def spawn(
        self, *, workload_executor, connection_string, driver_workload, startup_time=1
    ):
        LOGGER.info("Starting workload executor subprocess")

        try:
            os.remove(self.sentinel)
            LOGGER.debug(f"Cleaned up sentinel file at {self.sentinel}")
        except FileNotFoundError:
            pass

        try:
            os.remove(self.events)
            LOGGER.debug(f"Cleaned up events file at {self.events}")
        except FileNotFoundError:
            pass

        _args = [workload_executor, connection_string, json.dumps(driver_workload)]
        if not self.is_windows:
            args = _args
            self.workload_subprocess = subprocess.Popen(args, preexec_fn=os.setsid)  # noqa: PLW1509, S603
        else:
            args = ["C:/cygwin/bin/bash"]
            args.extend(_args)
            self.workload_subprocess = subprocess.Popen(
                args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP  # noqa: S603
            )

        LOGGER.debug(f"Subprocess argument list: {args}")
        LOGGER.info(f"Started workload executor [PID: {self.pid}]")

        try:
            # Wait for the workload executor to start.
            LOGGER.info(
                f"Waiting {startup_time} seconds for the workload executor "
                "subprocess to start"
            )
            self.workload_subprocess.wait(timeout=startup_time)
        except subprocess.TimeoutExpired:
            pass
        else:
            # We end up here if TimeoutExpired was not raised. This means that
            # the workload executor has already quit which is incorrect.
            raise WorkloadExecutorError(
                "Workload executor quit without receiving termination signal"
            )

        return self.workload_subprocess

    def stop(self):
        """Stop the process, verifying it didn't already exit."""

        LOGGER.info(f"Stopping workload executor [PID: {self.pid}]")

        try:
            if not self.is_windows:
                os.killpg(self.workload_subprocess.pid, signal.SIGINT)
            else:
                os.kill(self.workload_subprocess.pid, signal.CTRL_BREAK_EVENT)
        except ProcessLookupError as exc:
            raise PrematureExitError(
                "Could not request termination of workload executor, possibly because the workload executor exited prematurely: %s"
                % exc
            )

        # Since the default server selection timeout is 30 seconds,
        # allow up to 60 seconds for the workload executor to terminate.
        t_wait = 60
        try:
            self.workload_subprocess.wait(timeout=t_wait)
            LOGGER.info(f"Stopped workload executor [PID: {self.pid}]")
        except subprocess.TimeoutExpired:
            raise WorkloadExecutorError(
                f"The workload executor did not terminate {t_wait} seconds "
                "after sending the termination signal"
            )

        # Workload executors wrapped in shell scripts can report that they've
        # terminated earlier than they actually terminate on Windows.
        # One of the reasons for this that sometimes we need to write more than N milliones log lines to the file
        # In most cases, it's enough to have like 5-10 seconds delay here, but very rarely even 30 seconds was not enough, so set the safest value
        if self.is_windows:
            sleep(60)

        return self.read_stats()

    def read_stats(self):
        try:
            LOGGER.info(f"Reading sentinel file {self.sentinel!r}")
            with open(self.sentinel) as fp:
                stats = json.load(fp)
                LOGGER.info("Sentinel contains: %s" % json.dumps(stats))
                return stats
        except FileNotFoundError:
            LOGGER.error("Sentinel file not found")
            raise WorkloadExecutorError(
                "The workload executor did not write a results.json file in the expected location"
            )
        except json.JSONDecodeError:
            LOGGER.error("Sentinel file contains malformed JSON")
            raise WorkloadExecutorError(
                "The workload executor wrote a results.json that contained malformed JSON."
            )

    def terminate(self):
        """Stop the process if running. Use during cleanup."""

        try:
            if not self.is_windows:
                os.killpg(self.workload_subprocess.pid, signal.SIGINT)
            else:
                os.kill(self.workload_subprocess.pid, signal.CTRL_BREAK_EVENT)
        except ProcessLookupError:
            LOGGER.info(
                f"Workload executor process does not exist [PID: {self.pid}]"
            )

        # Since the default server selection timeout is 30 seconds,
        # allow up to 60 seconds for the workload executor to terminate.
        t_wait = 60
        try:
            self.workload_subprocess.wait(timeout=t_wait)
            LOGGER.info(f"Stopped workload executor [PID: {self.pid}]")
        except subprocess.TimeoutExpired:
            LOGGER.info(
                f"Workload executor is still running, trying to kill it [PID: {self.pid}]"
            )

            try:
                os.killpg(self.workload_subprocess.pid, signal.SIGKILL)
            except ProcessLookupError:
                # OK, process exited just as we were trying to kill it
                pass


def get_logs(admin_client, project, cluster_name):
    LOGGER.info(f"Retrieving logs for {cluster_name}")
    data = (
        admin_client.nds.groups[project.id]
        .clusters[cluster_name]
        .get(api_version="private")
        .data
    )

    if data["clusterType"] == "SHARDED":
        rtype = "CLUSTER"
        rname = data["deploymentItemName"]
    else:
        rtype = "REPLICASET"
        rname = data["deploymentItemName"]

    params = dict(
        resourceName=rname,
        resourceType=rtype,
        redacted=False,  # redaction on 4.4 servers in Atlas produces garbled log files. See https://jira.mongodb.org/browse/CLOUDP-87748 and https://jira.mongodb.org/projects/HELP/queues/issue/HELP-23629
        logTypes=[
            "FTDC",
            "MONGODB",
        ],  # ,'AUTOMATION_AGENT','MONITORING_AGENT','BACKUP_AGENT'],
        sizeRequestedPerFileBytes=100000000,
    )

    # Wait 10 minutes for logs to get collected.
    # This is a guess as to how long job collection might take, we haven't
    # investigated the actual times over a sufficiently large sample size.
    # The same timeout is used for retrying collection jobs and waiting for
    # any single collection job - if this turns out to be problematic,
    # we'll need to do some analysis of actual times to refine the timeouts.
    timeout = 600
    local = {}

    def collect():
        try:
            data = admin_client.groups[project.id].logCollectionJobs.post(**params).data
            job_id = data["id"]

            def check():
                data = (
                    admin_client.groups[project.id].logCollectionJobs[job_id].get().data
                )
                nonlocal local
                if data["status"] == "SUCCESS":
                    local["data"] = data
                    return True
                if data["status"] != "IN_PROGRESS":
                    raise AstrolabeTestCaseError(
                        "Unexpected log collection job status: %s: %s"
                        % (data["status"], data)
                    )
                # status == 'IN_PROGRESS', continue polling for logs to be ready
                return False

            poll(
                check,
                timeout=timeout,
                subject="log collection job '%s' for cluster '%s'"
                % (job_id, cluster_name),
            )

            if "downloadUrl" not in local["data"]:
                msg = "Log collection job did not produce a download url: %s" % data
                del local["data"]
                raise AstrolabeTestCaseError(msg)

            data = local["data"]
            LOGGER.info("Log download URL: %s" % data["downloadUrl"])
            # Assume the URL uses the same host as the other API requests, and
            # remove it so that we just have the path.
            url = re.sub(r"\w+://[^/]+", "", data["downloadUrl"])
            if url.startswith("/api"):
                url = url[4:]
            LOGGER.info("Retrieving %s" % url)
            resp = admin_client.request("GET", url)
            if resp.status_code != 200:
                raise AstrolabeTestCaseError(
                    "Request to %s failed: %s" % url, resp.status_code
                )
            # Note that this reads the entire response into memory, which might
            # fail for longer running workloads.
            local["archive_content"] = resp.response.content

            return True
        except Exception as e:
            LOGGER.error("Error retrieving logs for '%s': %s" % (cluster_name, e))
            # Poller will retry log collection.
            return False

    poll(
        collect,
        timeout=timeout,
        subject="log collection for cluster '%s'" % cluster_name,
    )

    with open("logs.tar.gz", "wb") as f:
        f.write(local["archive_content"])


def require_requests_ipv4():
    # Force requests to use IPv4.
    # If IPv4 endpoint times out, get that as the error
    # instead of trying IPv6 and receiving a protocol error.
    # https://stackoverflow.com/questions/33046733/force-requests-to-use-ipv4-ipv6

    def allowed_gai_family():
        """
        https://github.com/shazow/urllib3/blob/master/urllib3/util/connection.py
        """
        return socket.AF_INET

    urllib3_cn.allowed_gai_family = allowed_gai_family


def parse_iso8601_time(str):
    if str[-1] != "Z":
        raise ValueError("Only times ending in Z are supported")

    # Parse the ISO 8601 format timestamp. We need to keep the timezone offset so that all datetimes
    # are "offset-aware" and can be compared. The fromisoformat() parser doesn't support the "Z"
    # suffix, so replace it with the UTC time zone offset "+00:00", which the parser does support.
    return datetime.datetime.fromisoformat(str.replace("Z", "+00:00"))
