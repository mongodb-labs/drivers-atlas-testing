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

import logging, datetime, time as _time, gzip
import os, io, re
from time import sleep
from urllib.parse import urlencode

from pymongo import MongoClient
from tabulate import tabulate
import junitparser
import yaml

from .utils import mongo_client
from atlasclient import AtlasApiError, JSONObject
from astrolabe.commands import (
    get_one_organization_by_name, ensure_project, ensure_admin_user,
    ensure_connect_from_anywhere)
from astrolabe.exceptions import PollingTimeoutError
from astrolabe.exceptions import AstrolabeTestCaseError
from astrolabe.poller import BooleanCallablePoller
from astrolabe.utils import (
    assert_subset, get_cluster_name, get_test_name_from_spec_file,
    DriverWorkloadSubprocessRunner, SingleTestXUnitLogger,
    get_logs)
from .timer import Timer


LOGGER = logging.getLogger(__name__)


class AtlasTestCase:
    def __init__(self, *, client, admin_client, test_name, cluster_name, specification,
                 configuration):
        # Initialize.
        self.client = client
        self.admin_client = admin_client
        self.id = test_name
        self.cluster_name = cluster_name
        self.spec = specification
        self.config = configuration
        self.failed = False

        # Initialize attribute used for memoization of connection string.
        self.__connection_string = None

        # Initialize wrapper class for running workload executor.
        self.workload_runner = DriverWorkloadSubprocessRunner()

        # Validate and store organization and project.
        self.organization = get_one_organization_by_name(
            client=self.client,
            organization_name=self.config.organization_name)
        self.project = ensure_project(
            client=self.client, project_name=self.config.project_name,
            organization_id=self.organization.id)

    @property
    def cluster_url(self):
        return self.client.groups[self.project.id].clusters[
            self.cluster_name]

    def get_connection_string(self):
        if self.__connection_string is None:
            cluster = self.cluster_url.get().data
            uri = re.sub(r'://',
                '://%s:%s@' % (self.config.database_username, self.config.database_password),
                cluster.srvAddress)
            self.__connection_string = uri
        return self.__connection_string

    def __repr__(self):
        return "<AtlasTestCase: {}>".format(self.id)

    def is_cluster_state(self, goal_state):
        cluster_info = self.cluster_url.get().data
        return cluster_info.stateName.lower() == goal_state.lower()

    def verify_cluster_configuration_matches(self, expected_configuration):
        """Verify that the cluster config is what we expect it to be (based on
        maintenance status). Raises AssertionError."""
        cluster_config = self.cluster_url.get().data
        assert_subset(
            cluster_config,
            expected_configuration.clusterConfiguration)
        process_args = self.cluster_url.processArgs.get().data
        assert_subset(
            process_args, expected_configuration.processArgs)

    def initialize(self, no_create=False):
        """
        Initialize a cluster with the configuration required by the test
        specification.
        """
        
        if no_create:
            try:
                # If --no-create was specified and the cluster exists, skip
                # initialization. If the cluster does not exist, continue
                # with normal creation.
                self.cluster_url.get().data
                self.verify_cluster_configuration_matches(self.spec.initialConfiguration)
                return
            except AtlasApiError as exc:
                if exc.error_code != 'CLUSTER_NOT_FOUND':
                    LOGGER.warn('Cluster was not found, will create one')
            except AssertionError as exc:
                LOGGER.warn('Configuration did not match: %s. Recreating the cluster' % exc)
            
        LOGGER.info("Initializing cluster {!r}".format(self.cluster_name))

        cluster_config = self.spec.initialConfiguration.\
            clusterConfiguration.copy()
        cluster_config["name"] = self.cluster_name
        try:
            self.client.groups[self.project.id].clusters.post(
                **cluster_config)
        except AtlasApiError as exc:
            if exc.error_code == 'DUPLICATE_CLUSTER_NAME':
                # Cluster already exists. Simply re-configure it.
                # Cannot send cluster name when updating existing cluster.
                cluster_config.pop("name")
                self.client.groups[self.project.id].\
                    clusters[self.cluster_name].patch(**cluster_config)
            else:
                raise

        # Apply processArgs if provided.
        process_args = self.spec.initialConfiguration.processArgs
        if process_args:
            self.client.groups[self.project.id].\
                clusters[self.cluster_name].processArgs.patch(**process_args)

    def run(self, persist_cluster=False, startup_time=1):
        LOGGER.info("Running test {!r} on cluster {!r}".format(
            self.id, self.cluster_name))

        # Step-1: sanity-check the cluster configuration.
        self.verify_cluster_configuration_matches(self.spec.initialConfiguration)

        # Start the test timer.
        timer = Timer()
        timer.start()

        # Step-2: run driver workload.
        self.workload_runner.spawn(
            workload_executor=self.config.workload_executor,
            connection_string=self.get_connection_string(),
            driver_workload=self.spec.driverWorkload,
            startup_time=startup_time)

        for operation in self.spec.operations:
            if len(operation) != 1:
                raise ValueError("Operation must have exactly one key: %s" % operation)
                
            op_name, op_spec = list(operation.items())[0]
            
            if op_name == 'setClusterConfiguration':
                # Step-3: begin maintenance routine.
                final_config = op_spec
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

                # Step-4: wait until maintenance completes (cluster is IDLE).
                self.wait_for_idle()
                self.verify_cluster_configuration_matches(final_config)
                LOGGER.info("Cluster maintenance complete")
                
            elif op_name == 'testFailover':
                timer = Timer()
                timer.start()
                timeout = 300

                # DRIVERS-1585: failover may fail due to the cluster not being
                # ready. Retry failover up to a timeout if the
                # CLUSTER_RESTART_INVALID error is returned from the call
                while True:
                    try:
                        self.cluster_url['restartPrimaries'].post()
                    except AtlasApiError as exc:
                        if exc.error_code != 'CLUSTER_RESTART_INVALID':
                            raise
                    else:
                        break

                    if timer.elapsed > timeout:
                        raise PollingTimeoutError("Could not test failover as cluster wasn't ready")
                    else:
                        sleep(5)

                self.wait_for_idle()
                
            elif op_name == 'sleep':
                _time.sleep(op_spec)
                
            elif op_name == 'waitForIdle':
                self.wait_for_idle()
                
            elif op_name == 'restartVms':
                rv = self.admin_client.nds.groups[self.project.id].clusters[self.cluster_name].reboot.post(api_version='private')
                
                self.wait_for_idle()
                
            elif op_name == 'assertPrimaryRegion':
                region = op_spec['region']
                
                cluster_config = self.cluster_url.get().data
                timer = Timer()
                timer.start()
                timeout = op_spec.get('timeout', 90)
                
                with mongo_client(self.get_connection_string()) as mc:
                    while True:
                        rsc = mc.admin.command('replSetGetConfig')
                        member = [m for m in rsc['config']['members']
                            if m['horizons']['PUBLIC'] == '%s:%s' % mc.primary][0]
                        member_region = member['tags']['region']
                    
                        if region == member_region:
                            break
                            
                        if timer.elapsed > timeout:
                            raise Exception("Primary in cluster not in expected region '%s' (actual region '%s')" % (region, member_region))
                        else:
                            sleep(5)
                
            else:
                raise Exception('Unrecognized operation %s' % op_name)

        # Wait 10 seconds to ensure that the driver is not experiencing any
        # errors after the maintenance has concluded.
        sleep(10)
        
        # Step-5: interrupt driver workload and capture streams
        stats = self.workload_runner.stop()

        # Stop the timer
        timer.stop()

        # Step-6: compute xunit entry.
        junit_test = junitparser.TestCase(self.id)
        junit_test.time = timer.elapsed

        if (stats['numErrors'] != 0 or stats['numFailures'] != 0 or
                stats['numSuccesses'] == 0):
            LOGGER.info("FAILED: {!r}".format(self.id))
            self.failed = True
            # Write xunit logs for failed tests.
            junit_test.result = junitparser.Failure(str(stats))
        else:
            LOGGER.info("SUCCEEDED: {!r}".format(self.id))
            # Directly log output of successful tests as xunit output
            # is only visible for failed tests.

        LOGGER.info("Workload Statistics: {}".format(stats))
        
        get_logs(admin_client=self.admin_client,
            project=self.project, cluster_name=self.cluster_name)

        # Step 7: download logs asynchronously and delete cluster.
        # TODO: https://github.com/mongodb-labs/drivers-atlas-testing/issues/4
        if not persist_cluster:
            self.cluster_url.delete()
            LOGGER.info("Cluster {!r} marked for deletion.".format(
                self.cluster_name))

        return junit_test
        
    def wait_for_idle(self):
        # Small delay to account for Atlas not updating cluster state
        # synchronously potentially in all maintenance operations
        # (https://jira.mongodb.org/browse/PRODTRIAGE-1232).
        # VM restarts in sharded clusters require a much longer wait
        # (30+ seconds in some circumstances); scenarios that perform
        # VM restarts in sharded clusters should use explicit sleep operations
        # after the restarts until this is fixed.
        LOGGER.info("Waiting to wait for cluster %s to become idle" % self.cluster_name)
        sleep(5)
        LOGGER.info("Waiting for cluster %s to become idle" % self.cluster_name)
        timer = Timer()
        timer.start()
        ok = False
        timeout = self.config.polling_timeout
        wanted_state = 'idle'
        while timer.elapsed < timeout:
            cluster_info = self.cluster_url.get().data
            actual_state = cluster_info.stateName.lower()
            if actual_state == wanted_state:
                ok = True
                break
            LOGGER.info("Cluster %s: current state: %s; wanted state: %s; waited for %.1f sec" % (self.cluster_name, actual_state, wanted_state, timer.elapsed))
            sleep(1.0 / self.config.polling_frequency)
        if not ok:
            raise PollingTimeoutError("Polling timed out after %s seconds" % timeout)


class SpecTestRunnerBase:
    """Base class for spec test runners."""
    def __init__(self, *, client, admin_client, test_locator_token, configuration, xunit_output,
                 persist_clusters, no_create, workload_startup_time):
        self.cases = []
        self.client = client
        self.admin_client = admin_client
        self.config = configuration
        self.xunit_logger = SingleTestXUnitLogger(output_directory=xunit_output)
        self.persist_clusters = persist_clusters
        self.no_create = no_create
        self.workload_startup_time = workload_startup_time

        for full_path in self.find_spec_tests(test_locator_token):
            # Step-1: load test specification.
            with open(full_path, 'r') as spec_file:
                test_spec = JSONObject.from_dict(
                    yaml.safe_load(spec_file))

            # Step-2: generate test name.
            test_name = get_test_name_from_spec_file(full_path)

            # Step-3: generate unique cluster name.
            cluster_name = get_cluster_name(test_name, self.config.name_salt)

            self.cases.append(
                AtlasTestCase(client=self.client, admin_client=self.admin_client,
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
        pro_name = self.config.project_name
        LOGGER.info("Verifying project {!r}".format(pro_name))
        project = ensure_project(
            client=self.client, project_name=pro_name, organization_id=org.id)
        LOGGER.info("Successfully verified project {!r}".format(pro_name))

        # Step-3: create a user under the project.
        # Note: all test operations will be run as this user.
        uname = self.config.database_username
        LOGGER.info("Verifying user {!r}".format(uname))
        ensure_admin_user(
            client=self.client, project_id=project.id,
            username=uname, password=self.config.database_password)
        LOGGER.info("Successfully verified user {!r}".format(uname))

        # Step-4: populate project IP whitelist to allow access from anywhere.
        LOGGER.info("Enabling access from anywhere on project "
                    "{!r}".format(pro_name))
        ensure_connect_from_anywhere(client=self.client, project_id=project.id)
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
            case.initialize(no_create=self.no_create)

        # Step-2: run tests round-robin until all have been run.
        remaining_test_cases = self.cases.copy()
        while remaining_test_cases:
            active_case = remaining_test_cases[0]

            # Select a case whose cluster is ready.
            active_case.wait_for_idle()
            LOGGER.info("Test cluster {!r} is ready".format(
                active_case.cluster_name))

            # Run the case.
            xunit_test = active_case.run(persist_cluster=self.persist_clusters,
                                         startup_time=self.workload_startup_time)
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
