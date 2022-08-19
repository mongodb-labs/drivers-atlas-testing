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
import subprocess
import time

import junitparser
import yaml
from atlasclient.utils import JSONObject

from astrolabe.utils import DriverWorkloadSubprocessRunner

from .timer import Timer

LOGGER = logging.getLogger(__name__)


class KubernetesTest:
    """
    The Kubernetes test runner.
    """

    def __init__(
        self,
        *,
        name,
        spec_test_file,
        workload_file,
        workload_executor,
        connection_string,
    ):
        """
        Create a Kubernetes test runner.

        :Parameters:
          - `name` (string): the test name
          - `spec_test_file` (string): path to the Kubernetes test file
          - `workload_file` (string): path to the workload file
          - `workload_executor` (string): path to the workload executor binary or script
          - `connection_string` (string): the MongoDB connection string to give to the workload exeuctor
        """

        self.name = name
        self.spec_test_file = spec_test_file
        self.workload_file = workload_file
        self.workload_executor = workload_executor
        self.connection_string = connection_string

        self.failed = False

        # Initialize wrapper class for running workload executor.
        self.workload_runner = DriverWorkloadSubprocessRunner()

    def run(self, startup_time=1):
        """
        Run the Kubernetes test.

        :Parameters:
          - `startup_time` (int): the amount of time in seconds to wait for the workload executor to
            start
        """

        LOGGER.info(
            f"Running test {self.name} using test file {self.spec_test_file} and workload file {self.workload_file}"
        )

        with open(self.spec_test_file) as f:
            test = JSONObject.from_dict(yaml.safe_load(f))

        with open(self.workload_file) as f:
            workload = JSONObject.from_dict(yaml.safe_load(f))

        # Start the test timer. The timer times the duration of the workload executor.
        timer = Timer()
        timer.start()

        # Run driver workload.
        self.workload_runner.spawn(
            workload_executor=self.workload_executor,
            connection_string=self.connection_string,
            driver_workload=workload,
            startup_time=startup_time,
        )

        try:
            for operation in test.operations:
                # Ensure that there is only one key per operation object.
                if len(operation) != 1:
                    raise ValueError(
                        f"Operation must have exactly one key: {operation}"
                    )

                op_name, op_val = list(operation.items())[0]

                if op_name == "kubectl":
                    # The "kubectl" operation runs a command with the kubectl CLI. The value is an
                    # array of the command arguments. Note that the kubectl executable must be in
                    # the system PATH.
                    command = ["kubectl"] + op_val
                    LOGGER.info(f"Running command {command}")
                    subprocess.run(command)
                elif op_name == "sleep":
                    # The "sleep" operation sleeps for N seconds.
                    LOGGER.info(f"Sleeping for {op_val}s")
                    time.sleep(op_val)
                else:
                    raise Exception(f"Unrecognized operation {op_name}")

            # Wait 10 seconds to ensure that the driver is not experiencing any
            # errors after the maintenance has concluded.
            time.sleep(10)

            # Interrupt driver workload and capture streams.
            stats = self.workload_runner.stop()

            timer.stop()

            junit_test = junitparser.TestCase(self.name)
            junit_test.time = timer.elapsed

            if (
                stats["numErrors"] != 0
                or stats["numFailures"] != 0
                or stats["numSuccesses"] == 0
            ):
                LOGGER.info(f"FAILED: {self.name!r}")
                self.failed = True
                # Write xunit logs for failed tests.
                junit_test.result = junitparser.Failure(str(stats))
            else:
                LOGGER.info(f"SUCCEEDED: {self.name!r}")
                # Directly log output of successful tests as xunit output
                # is only visible for failed tests.

            LOGGER.info(f"Workload Statistics: {stats}")

            return junit_test
        finally:
            self.workload_runner.terminate()
