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
import yaml

from atlasclient import JSONObject
from astrolabe.exceptions import WorkloadExecutorError
from astrolabe.utils import DriverWorkloadSubprocessRunner


class ValidateWorkloadExecutor(TestCase):
    WORKLOAD_EXECUTOR = None
    CONNECTION_STRING = None
    STARTUP_TIME = None

    def setUp(self):
        self.client = MongoClient(self.CONNECTION_STRING, w='majority')

    def run_test(self, driver_workload):
        # Set self.coll for future use of the validator, such that it can
        # read the data inserted into the collection.
        # Actual insertion of initial data isn't done via this object.
        dbname = None
        collname = None
        for e in driver_workload['createEntities']:
            if dbname and collname:
                break
            if dbname is None and 'database' in e:
                dbname = e['database']['databaseName']
            elif collanme is None and 'collection' in e:
                collname = e['collection']['collectionName']

        if not (dbname and collname):
            self.fail('Invalid scenario: executor validator test cases must provide database and collection entities')

        self.coll = self.client.get_database(dbname).get_collection(collname)
        
        subprocess = DriverWorkloadSubprocessRunner()
        try:
            subprocess.spawn(workload_executor=self.WORKLOAD_EXECUTOR,
                             connection_string=self.CONNECTION_STRING,
                             driver_workload=driver_workload,
                             startup_time=self.STARTUP_TIME)
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
        driver_workload = JSONObject.from_dict(
            yaml.load(open('tests/validator-simple.yml').read(), Loader=yaml.FullLoader)['driverWorkload']
        )

        stats = self.run_test(driver_workload)

        num_reported_updates = stats['numSuccesses']
        update_count = self.coll.find_one(
            {'_id': 'validation_sentinel'})['count']
        if abs(num_reported_updates - update_count) > 1:
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
        driver_workload = JSONObject.from_dict(
            yaml.load(open('tests/validator-numErrors.yml').read(), Loader=yaml.FullLoader)['driverWorkload']
        )

        stats = self.run_test(driver_workload)

        num_reported_updates = stats['numSuccesses']
        update_count = self.coll.find_one(
            {'_id': 'validation_sentinel'})['count']
        if abs(num_reported_updates - update_count) > 1:
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

    def test_num_failures(self):
        driver_workload = JSONObject.from_dict(
            yaml.load(open('tests/validator-numFailures.yml').read(), Loader=yaml.FullLoader)['driverWorkload']
        )

        stats = self.run_test(driver_workload)

        num_reported_finds = stats['numSuccesses']

        num_reported_failures = stats['numFailures']
        if abs(num_reported_failures - num_reported_finds) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected approximately {} errored operations "
                "to be reported, got {} instead.".format(
                    num_reported_finds, num_reported_failures))


def validator_factory(workload_executor, connection_string, startup_time):
    ValidateWorkloadExecutor.WORKLOAD_EXECUTOR = workload_executor
    ValidateWorkloadExecutor.CONNECTION_STRING = connection_string
    ValidateWorkloadExecutor.STARTUP_TIME = startup_time
    return ValidateWorkloadExecutor
