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

import os, os.path
from copy import deepcopy
from subprocess import TimeoutExpired
from time import sleep
from unittest import TestCase

from pymongo import MongoClient
import yaml

from atlasclient import JSONObject
from astrolabe.exceptions import WorkloadExecutorError, PrematureExitError
from astrolabe.utils import DriverWorkloadSubprocessRunner


class ValidateWorkloadExecutor(TestCase):
    WORKLOAD_EXECUTOR = None
    CONNECTION_STRING = None
    STARTUP_TIME = None

    def setUp(self):
        self.client = MongoClient(self.CONNECTION_STRING, w='majority')

    def set_collection_from_workload(self, driver_workload):
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
            elif collname is None and 'collection' in e:
                collname = e['collection']['collectionName']

        if not (dbname and collname):
            self.fail('Invalid scenario: executor validator test cases must provide database and collection entities')

        self.coll = self.client.get_database(dbname).get_collection(collname)
    
    def run_test(self, driver_workload):
        self.set_collection_from_workload(driver_workload)
        
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
            stats = subprocess.stop()
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
    
    def run_test_expecting_error(self, driver_workload):
        self.set_collection_from_workload(driver_workload)
        
        subprocess = DriverWorkloadSubprocessRunner()
        try:
            subprocess.spawn(workload_executor=self.WORKLOAD_EXECUTOR,
                             connection_string=self.CONNECTION_STRING,
                             driver_workload=driver_workload,
                             startup_time=self.STARTUP_TIME)

            # Run operations for 5 seconds.
            sleep(5)
        except WorkloadExecutorError:
            # Accept premature workload executor exits when expecting the
            # run to error.
            pass

        try:
            stats = subprocess.stop()
        except PrematureExitError:
            # OK for workload executor to exit prematurely when we expect
            # it to fail with an error. We still need to return stats.
            stats = subprocess.read_stats()
        except TimeoutExpired:
            self.fail("The workload executor did not terminate soon after "
                      "receiving the termination signal.")

        return stats

    def test_simple(self):
        driver_workload = JSONObject.from_dict(
            yaml.safe_load(open('tests/validator-simple.yml').read())['driverWorkload']
        )
        
        if os.path.exists('events.json'):
            os.unlink('events.json')

        stats = self.run_test(driver_workload)

        num_successes = stats['numSuccesses']
        update_count = self.coll.find_one(
            {'_id': 'validation_sentinel'})['count']
        if abs(num_successes/2 - update_count) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected 2*{} successful "
                "operations to be reported, got {} instead.".format(
                    update_count, num_successes))
        if abs(stats['numIterations'] - update_count) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected {} iterations "
                "to be reported, got {} instead.".format(
                    update_count, stats['numIterations']))
        if update_count == 0:
            self.fail(
                "The workload executor didn't execute any operations "
                "or didn't execute them appropriately.")
                
        _events = yaml.safe_load(open('events.json').read())
        if 'events' not in _events:
            self.fail(
                "The workload executor didn't record events as expected.")
        events = _events['events']
        connection_events = [event for event in events
            if event['name'].startswith('Connection')]
        if not connection_events:
            self.fail(
                "The workload executor didn't record connection events as expected.")
        pool_events = [event for event in events
            if event['name'].startswith('Pool')]
        if not pool_events:
            self.fail(
                "The workload executor didn't record connection pool events as expected.")
        command_events = [event for event in events
            if event['name'].startswith('Command')]
        if not command_events:
            self.fail(
                "The workload executor didn't record command events as expected.")
        for event_list in [connection_events, pool_events, command_events]:
            for event in event_list:
                if 'name' not in event:
                    self.fail(
                        "The workload executor didn't record event name as expected.")
                if not event['name'].endswith('Event'):
                    self.fail(
                        "The workload executor didn't record event name as expected.")
                if 'observedAt' not in event:
                    self.fail(
                        "The workload executor didn't record observation time as expected.")

    def test_num_errors(self):
        driver_workload = JSONObject.from_dict(
            yaml.safe_load(open('tests/validator-numErrors.yml').read())['driverWorkload']
        )

        stats = self.run_test(driver_workload)

        num_successes = stats['numSuccesses']
        update_count = self.coll.find_one(
            {'_id': 'validation_sentinel'})['count']
        if abs(num_successes/2 - update_count) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected 2*{} successful "
                "operations to be reported, got {} instead.".format(
                    update_count, num_successes))

        num_reported_errors = stats['numErrors']
        if abs(num_reported_errors - num_successes/2) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected approximately {}/2 errored operations "
                "to be reported, got {} instead.".format(
                    num_successes, num_reported_errors))
        if abs(stats['numIterations'] - update_count) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected {} iterations "
                "to be reported, got {} instead.".format(
                    update_count, stats['numIterations']))

    def test_num_errors_not_captured(self):
        driver_workload = JSONObject.from_dict(
            yaml.safe_load(open('tests/validator-numErrors-not-captured.yml').read())['driverWorkload']
        )

        stats = self.run_test_expecting_error(driver_workload)

        num_reported_errors = stats['numErrors']
        if num_reported_errors != -1:
            self.fail(
                "The workload executor reported unexpected execution "
                "statistics. Expected -1 errors since errors were not captured, "
                "got {} instead.".format(
                    num_reported_errors))

    def test_num_failures(self):
        driver_workload = JSONObject.from_dict(
            yaml.safe_load(open('tests/validator-numFailures.yml').read())['driverWorkload']
        )

        stats = self.run_test(driver_workload)

        num_reported_finds = stats['numSuccesses']

        num_reported_failures = stats['numFailures']
        if abs(num_reported_failures - num_reported_finds/2) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected approximately {}/2 errored operations "
                "to be reported, got {} instead.".format(
                    num_reported_finds, num_reported_failures))
        if abs(stats['numIterations'] - num_reported_finds/2) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected {} iterations "
                "to be reported, got {} instead.".format(
                    num_reported_finds, stats['numIterations']))

    def test_num_failures_not_captured(self):
        driver_workload = JSONObject.from_dict(
            yaml.safe_load(open('tests/validator-numFailures-not-captured.yml').read())['driverWorkload']
        )

        stats = self.run_test_expecting_error(driver_workload)

        num_reported_errors = stats['numFailures']
        if num_reported_errors != -1:
            self.fail(
                "The workload executor reported unexpected execution "
                "statistics. Expected -1 failures since failures were not captured, "
                "got {} instead.".format(
                    num_reported_errors))

    def test_num_failures_as_errors(self):
        driver_workload = JSONObject.from_dict(
            yaml.safe_load(open('tests/validator-numFailures-as-errors.yml').read())['driverWorkload']
        )

        stats = self.run_test(driver_workload)

        num_reported_finds = stats['numSuccesses']

        num_reported_errors = stats['numErrors']
        num_reported_failures = stats['numFailures']
        if abs(num_reported_errors - num_reported_finds/2) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected approximately {}/2 errored operations "
                "to be reported, got {} instead.".format(
                    num_reported_finds, num_reported_failures))
        if num_reported_failures > 0:
            self.fail(
                "The workload executor reported unexpected execution "
                "statistics. Expected all failures to be reported as errors, "
                "got {} failures instead.".format(
                    num_reported_failures))
        if abs(stats['numIterations'] - num_reported_finds/2) > 1:
            self.fail(
                "The workload executor reported inconsistent execution "
                "statistics. Expected {} iterations "
                "to be reported, got {} instead.".format(
                    num_reported_finds, stats['numIterations']))


def validator_factory(workload_executor, connection_string, startup_time):
    ValidateWorkloadExecutor.WORKLOAD_EXECUTOR = workload_executor
    ValidateWorkloadExecutor.CONNECTION_STRING = connection_string
    ValidateWorkloadExecutor.STARTUP_TIME = startup_time
    return ValidateWorkloadExecutor
