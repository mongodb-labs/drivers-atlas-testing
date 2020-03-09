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

from hashlib import sha256
import json
import logging
import os
import signal
import subprocess
import sys
from time import sleep
from urllib.parse import urlencode

from pymongo import MongoClient
from tabulate import tabulate
import junitparser
import yaml

from atlasclient import AtlasApiError, JSONObject
from astrolabe.commands import (
    get_one_organization_by_name, ensure_project, ensure_admin_user,
    ensure_connect_from_anywhere)
from astrolabe.exceptions import AstrolabeTestCaseError
from astrolabe.poller import BooleanCallablePoller
from astrolabe.utils import (
    assert_subset, cached_property, encode_cdata, SingleTestXUnitLogger,
    Timer)


LOGGER = logging.getLogger(__name__)


class AtlasTestCase:
    def __init__(self, *, client, test_name, cluster_name, specification,
                 configuration):
        # Initialize.
        self.client = client
        self.id = test_name
        self.cluster_name = cluster_name
        self.spec = specification
        self.config = configuration
        self.failed = False

        # Account for platform-specific interrupt signals.
        if sys.platform != 'win32':
            self.sigint = signal.SIGINT
        else:
            self.sigint = signal.CTRL_C_EVENT

        # Validate organization and group.
        self.get_organization()
        self.get_group()

    @cached_property
    def get_organization(self):
        return get_one_organization_by_name(
            client=self.client,
            organization_name=self.config.organization_name)

    @cached_property
    def get_group(self):
        return ensure_project(
            client=self.client, group_name=self.config.group_name,
            organization_id=self.get_organization().id)

    @property
    def cluster_url(self):
        return self.client.groups[self.get_group().id].clusters[
            self.cluster_name]

    @cached_property
    def get_connection_string(self):
        cluster = self.cluster_url.get().data
        prefix, suffix = cluster.srvAddress.split("//")
        uri_options = self.spec.maintenancePlan.uriOptions.copy()

        # Boolean options must be converted to lowercase strings.
        for key, value in uri_options.items():
            if isinstance(value, bool):
                uri_options[key] = str(value).lower()

        connection_string = (prefix + "//" + self.config.database_username
                             + ":" + self.config.database_password + "@"
                             + suffix + "/?")
        connection_string += urlencode(uri_options)
        return connection_string

    def __repr__(self):
        return "<AtlasTestCase: {}>".format(self.id)

    def is_cluster_state(self, goal_state):
        cluster_info = self.cluster_url.get().data
        return cluster_info.stateName.lower() == goal_state.lower()

    def verify_cluster_configuration_matches(self, state):
        """Verify that the cluster config is what we expect it to be (based on
        maintenance status). Raises AssertionError."""
        state = state.lower()
        if state not in ("initial", "final"):
            raise AstrolabeTestCaseError(
                "State must be either 'initial' or 'final'.")
        cluster_config = self.cluster_url.get().data
        assert_subset(
            cluster_config,
            self.spec.maintenancePlan[state].clusterConfiguration)
        process_args = self.cluster_url.processArgs.get().data
        assert_subset(
            process_args, self.spec.maintenancePlan[state].processArgs)

    def initialize(self):
        """
        Initialize a cluster with the configuration required by the test
        specification.
        """
        LOGGER.info("Initializing cluster {!r}".format(self.cluster_name))

        cluster_config = self.spec.maintenancePlan.initial.\
            clusterConfiguration.copy()
        cluster_config["name"] = self.cluster_name
        try:
            self.client.groups[self.get_group().id].clusters.post(
                **cluster_config)
        except AtlasApiError as exc:
            if exc.error_code == 'DUPLICATE_CLUSTER_NAME':
                # Cluster already exists. Simply re-configure it.
                # Cannot send cluster name when updating existing cluster.
                cluster_config.pop("name")
                self.client.groups[self.get_group().id].\
                    clusters[self.cluster_name].patch(**cluster_config)

        # Apply processArgs if provided.
        process_args = self.spec.maintenancePlan.initial.processArgs
        if process_args:
            self.client.groups[self.get_group().id].\
                clusters[self.cluster_name].processArgs.patch(**process_args)

    def run(self, persist_cluster=False):
        LOGGER.info("Running test {!r} on cluster {!r}".format(
            self.id, self.cluster_name))

        # Step-0: sanity-check the cluster configuration.
        self.verify_cluster_configuration_matches("initial")

        # Start the test timer.
        timer = Timer()
        timer.start()

        # Step-1: load test data.
        test_data = self.spec.driverWorkload.get('testData')
        if test_data:
            LOGGER.info("Loading test data on cluster {!r}".format(
                self.cluster_name))
            connection_string = self.get_connection_string()
            client = MongoClient(connection_string, w="majority")
            coll = client.get_database(
                self.spec.driverWorkload.database).get_collection(
                self.spec.driverWorkload.collection)
            coll.drop()
            coll.insert_many(test_data)
            LOGGER.info("Successfully loaded test data on cluster {!r}".format(
                self.cluster_name))

        # Step-2: run driver workload.
        LOGGER.info("Starting workload executor")
        connection_string = self.get_connection_string()
        driver_workload = json.dumps(self.spec.driverWorkload)
        worker_subprocess = subprocess.Popen([
            self.config.workload_executor, connection_string,
            driver_workload], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        LOGGER.info("Started workload executor [PID: {}]".format(
            worker_subprocess.pid))

        # Step-3: begin maintenance routine.
        final_config = self.spec.maintenancePlan.final
        cluster_config = final_config.clusterConfiguration
        process_args = final_config.processArgs

        if not cluster_config and not process_args:
            raise RuntimeError("invalid maintenance plan")

        if cluster_config:
            LOGGER.info("Pushing cluster configuration update")
            self.cluster_url.patch(**cluster_config)

        if process_args:
            LOGGER.info("Pushing process arguments update")
            self.cluster_url.processArgs.patch(**process_args)

        # Sleep before polling to avoid "missing" cluster.stateName change.
        sleep(3)

        # Step-4: wait until maintenance completes (cluster is IDLE).
        selector = BooleanCallablePoller(
            frequency=self.config.polling_frequency,
            timeout=self.config.polling_timeout)
        LOGGER.info("Waiting for cluster maintenance to complete")
        selector.poll([self], attribute="is_cluster_state", args=("IDLE",),
                      kwargs={})
        self.verify_cluster_configuration_matches("final")
        LOGGER.info("Cluster maintenance complete")

        # Step-5: interrupt driver workload and capture streams
        LOGGER.info("Stopping workload executor [PID: {}]".format(
            worker_subprocess.pid))
        os.kill(worker_subprocess.pid, self.sigint)
        stdout, stderr = worker_subprocess.communicate(timeout=10)

        LOGGER.info("Stopped workload executor")

        # Stop the timer
        timer.stop()

        # Step-6: compute xunit entry.
        junit_test = junitparser.TestCase(self.id)
        junit_test.time = timer.elapsed
        if worker_subprocess.returncode != 0:
            LOGGER.info("FAILED: {!r}".format(self.id))
            self.failed = True
            errmsg = """
            Number of errors: {numErrors}
            Number of failures: {numFailures}    
            """
            try:
                err_info = json.loads(stderr)
                junit_test.result = junitparser.Failure(
                    errmsg.format(**err_info))
            except json.JSONDecodeError:
                junit_test.result = junitparser.Error(encode_cdata(stderr))
        else:
            LOGGER.info("SUCCEEDED: {!r}".format(self.id))
        junit_test.system_err = encode_cdata(stderr)
        junit_test.system_out = encode_cdata(stdout)

        # Step 7: download logs asynchronously and delete cluster.
        # TODO: https://github.com/mongodb-labs/drivers-atlas-testing/issues/4
        if not persist_cluster:
            self.cluster_url.delete()
            LOGGER.info("Cluster {!r} marked for deletion.".format(
                self.cluster_name))

        return junit_test


class SpecTestRunnerBase:
    """Base class for spec test runners."""
    def __init__(self, *, client, test_locator_token, configuration, xunit_output,
                 persist_clusters):
        self.cases = []
        self.client = client
        self.config = configuration
        self.xunit_logger = SingleTestXUnitLogger(output_directory=xunit_output)
        self.persist_clusters = persist_clusters

        for full_path in self.find_spec_tests(test_locator_token):
            # Step-1: load test specification.
            with open(full_path, 'r') as spec_file:
                test_spec = JSONObject.from_dict(
                    yaml.load(spec_file, Loader=yaml.FullLoader))

            # Step-2: generate test name.
            _, filename = os.path.split(full_path)
            test_name = os.path.splitext(filename)[0].replace('-', '_')

            # Step-3: generate unique cluster name.
            name_hash = sha256(test_name.encode('utf-8'))
            name_hash.update(self.config.name_salt.encode('utf-8'))
            cluster_name = name_hash.hexdigest()[:10]

            self.cases.append(
                AtlasTestCase(client=self.client,
                              test_name=test_name,
                              cluster_name=cluster_name,
                              specification=test_spec,
                              configuration=self.config))

        # Set up Atlas for tests.
        # Step-1: ensure validity of the organization.
        # Note: organizations can only be created by via the web UI.
        org_name = self.config.organization_name
        LOGGER.info("Verifying organization {!r}".format(org_name))
        org = get_one_organization_by_name(
            client=self.client, organization_name=org_name)
        LOGGER.info("Successfully verified organization {!r}".format(org_name))

        # Step-2: check that the project exists or else create it.
        pro_name = self.config.group_name
        LOGGER.info("Verifying project {!r}".format(pro_name))
        group = ensure_project(
            client=self.client, group_name=pro_name, organization_id=org.id)
        LOGGER.info("Successfully verified project {!r}".format(pro_name))

        # Step-3: create a user under the project.
        # Note: all test operations will be run as this user.
        uname = self.config.database_username
        LOGGER.info("Verifying user {!r}".format(uname))
        ensure_admin_user(
            client=self.client, group_id=group.id,
            username=uname, password=self.config.database_password)
        LOGGER.info("Successfully verified user {!r}".format(uname))

        # Step-4: populate project IP whitelist to allow access from anywhere.
        LOGGER.info("Enabling access from anywhere on project "
                    "{!r}".format(pro_name))
        ensure_connect_from_anywhere(client=self.client, group_id=group.id)
        LOGGER.info("Successfully enabled access from anywhere on project "
                    "{!r}".format(pro_name))

        # Step-5: log test plan.
        LOGGER.info(self.get_printable_test_plan())

    @staticmethod
    def find_spec_tests(test_locator_token):
        raise NotImplementedError

    def get_printable_test_plan(self):
        table_data = []
        for test_case in self.cases:
            table_data.append([test_case.id, test_case.cluster_name])
        table_txt = "Astrolabe Test Plan\n{}\n"
        return table_txt.format(tabulate(
            table_data, headers=["Test name", "Atlas cluster name"],
            tablefmt="rst"))

    def run(self):
        # Step-0: sentinel flag to track failure/success.
        failed = False

        # Step-1: initialize tests clusters
        for case in self.cases:
            case.initialize()

        # Step-2: run tests round-robin until all have been run.
        remaining_test_cases = self.cases.copy()
        while remaining_test_cases:
            selector = BooleanCallablePoller(
                frequency=self.config.polling_frequency,
                timeout=self.config.polling_timeout)

            # Select a case whose cluster is ready.
            LOGGER.info("Waiting for a test cluster to become ready")
            active_case = selector.poll(
                remaining_test_cases, attribute="is_cluster_state",
                args=("IDLE",), kwargs={})
            LOGGER.info("Test cluster {!r} is ready".format(
                active_case.cluster_name))

            # Run the case.
            xunit_test = active_case.run(persist_cluster=self.persist_clusters)
            # Write xunit entry for case.
            self.xunit_logger.write_xml(
                test_case=xunit_test,
                filename=active_case.id)
            # Remove completed case from list.
            remaining_test_cases.remove(active_case)
            # Update tracker.
            failed = failed or active_case.failed

        return failed


class SingleTestRunner(SpecTestRunnerBase):
    """Run the spec test file named ``test_locator_token``."""
    @staticmethod
    def find_spec_tests(test_locator_token):
        """
        Verify that the given file is a spec test file and return its
        absolute path.
        """
        LOGGER.info("Loading spec test from file {!r}".format(
            test_locator_token))
        full_path = os.path.realpath(test_locator_token)
        if (os.path.isfile(full_path) and
                test_locator_token.lower().endswith(('.yml', 'yaml'))):
            yield full_path


class MultiTestRunner(SpecTestRunnerBase):
    """Run all spec test files in the ``test_locator_token`` directory."""
    @staticmethod
    def find_spec_tests(test_locator_token):
        LOGGER.info("Scanning directory {!r} for spec tests".format(
            test_locator_token))
        for root, dirs, files in os.walk(test_locator_token):
            for file in files:
                full_path = os.path.join(root, file)
                if (os.path.isfile(full_path) and
                        file.lower().endswith(('.yml', 'yaml'))):
                    LOGGER.debug("Loading spec test from file {!r}".format(
                        full_path))
                    yield full_path
