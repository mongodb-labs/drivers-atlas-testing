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

from copy import deepcopy
from subprocess import TimeoutExpired
from time import sleep
from unittest import TestCase

from pymongo import MongoClient

from atlasclient import JSONObject
from astrolabe.exceptions import WorkloadExecutorError
from astrolabe.utils import DriverWorkloadSubprocessRunner, load_test_data


DRIVER_WORKLOAD = JSONObject.from_dict({
    'database': 'validation_db',
    'collection': 'validation_coll',
    'testData': [{'_id': 'validation_sentinel', 'count': 0}],
    'operations': []
})


class ValidateWorkloadExecutor(TestCase):
    WORKLOAD_EXECUTOR = None
    CONNECTION_STRING = None
    STARTUP_TIME = None

    def setUp(self):
        self.client = MongoClient(self.CONNECTION_STRING, w='majority')
        self.coll = self.client.get_database(
            DRIVER_WORKLOAD['database']).get_collection(
            DRIVER_WORKLOAD['collection'])
        load_test_data(self.CONNECTION_STRING, DRIVER_WORKLOAD)

    def run_test(self, driver_workload):
        subprocess = DriverWorkloadSubprocessRunner()
        try:
            subprocess.spawn(workload_executor=self.WORKLOAD_EXECUTOR,
                             connection_string=self.CONNECTION_STRING,
                             driver_workload=driver_workload)
            # Wait for the executor to start.
            sleep(self.STARTUP_TIME)
        except WorkloadExecutorError:
            outs, errs = subprocess.workload_subprocess.communicate(timeout=2)
            self.fail("The workload executor terminated prematurely before "
                      "receiving the termination signal.\n"
                      "STDOUT: {!r}\nSTDERR: {!r}".format(outs, errs))

        # Run operations for 5 seconds.
        sleep(5)

        try:
            stats = subprocess.terminate()
        except TimeoutExpired:
            self.fail("The workload executor did not terminate soon after "
                      "receiving the termination signal.")

        # Check that results.json is actually written.
        if all(val == -1 for val in stats.values()):
            self.fail("The workload executor did not write a results.json "
                      "file in the expected location, or the file that was "
                      "written contained malformed JSON.")

        if any(val < 0 for val in stats.values()):
            self.fail("The workload executor reported incorrect execution "
                      "statistics. Reported statistics MUST NOT be negative.")

        return stats

    def test_simple(self):
        operations = [
            {'object': 'collection',
             'name': 'updateOne',
             'arguments': {
                 'filter': {'_id': 'validation_sentinel'},
                 'update': {'$inc': {'count': 1}}}}]
        driver_workload = deepcopy(DRIVER_WORKLOAD)
        driver_workload['operations'] = operations
        driver_workload = JSONObject.from_dict(driver_workload)

        stats = self.run_test(driver_workload)

        num_reported_updates = stats['numSuccesses']
        update_count = self.coll.find_one(
            {'_id': 'validation_sentinel'})['count']
        if update_count != num_reported_updates:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected {} successful "
                "updates to be reported, got {} instead.".format(
                    update_count, num_reported_updates))
        if update_count == 0:
            self.fail(
                "The workload executor didn't execute any operations "
                "or didn't execute them appropriately.")

    def test_num_errors(self):
        operations = [
            {'object': 'collection',
             'name': 'updateOne',
             'arguments': {
                 'filter': {'_id': 'validation_sentinel'},
                 'update': {'$inc': {'count': 1}}}},
            {'object': 'collection',
             'name': 'doesNotExist',
             'arguments': {'foo': 'bar'}}]
        driver_workload = deepcopy(DRIVER_WORKLOAD)
        driver_workload['operations'] = operations
        driver_workload = JSONObject.from_dict(driver_workload)

        stats = self.run_test(driver_workload)

        num_reported_updates = stats['numSuccesses']
        update_count = self.coll.find_one(
            {'_id': 'validation_sentinel'})['count']
        if update_count != num_reported_updates:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected {} successful "
                "updates to be reported, got {} instead.".format(
                    update_count, num_reported_updates))

        num_reported_errors = stats['numErrors']
        if abs(num_reported_errors - num_reported_updates) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected approximately {} errored operations "
                "to be reported, got {} instead.".format(
                    num_reported_updates, num_reported_errors))


def validator_factory(workload_executor, connection_string, startup_time):
    ValidateWorkloadExecutor.WORKLOAD_EXECUTOR = workload_executor
    ValidateWorkloadExecutor.CONNECTION_STRING = connection_string
    ValidateWorkloadExecutor.STARTUP_TIME = startup_time
    return ValidateWorkloadExecutor
