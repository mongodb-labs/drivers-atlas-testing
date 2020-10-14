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
import os, io
from time import sleep, monotonic
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
    assert_subset, get_cluster_name, get_test_name_from_spec_file,
    load_test_data, DriverWorkloadSubprocessRunner, SingleTestXUnitLogger,
    Timer)


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
            prefix, suffix = cluster.srvAddress.split("//")
            uri_options = self.spec.uriOptions.copy()

            # Boolean options must be converted to lowercase strings.
            for key, value in uri_options.items():
                if isinstance(value, bool):
                    uri_options[key] = str(value).lower()

            connection_string = (prefix + "//" + self.config.database_username
                                 + ":" + self.config.database_password + "@"
                                 + suffix + "/?")
            connection_string += urlencode(uri_options)
            self.__connection_string = connection_string
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
        
        self.start_time = _time.time()
        
        if no_create:
            return
            
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

        # Step-0: sanity-check the cluster configuration.
        self.verify_cluster_configuration_matches(self.spec.initialConfiguration)

        # Start the test timer.
        timer = Timer()
        timer.start()

        # Step-1: load test data.
        test_datas = self.spec.driverWorkload.get('initialData')
        if test_datas:
            LOGGER.info("Loading test data on cluster {!r}".format(
                self.cluster_name))
            connection_string = self.get_connection_string()
            load_test_data(connection_string, self.spec.driverWorkload)
            LOGGER.info("Successfully loaded test data on cluster {!r}".format(
                self.cluster_name))

        # Step-2: run driver workload.
        self.workload_runner.spawn(
            workload_executor=self.config.workload_executor,
            connection_string=self.get_connection_string(),
            driver_workload=self.spec.driverWorkload,
            startup_time=startup_time)

        for operation in self.spec.operations:
            if hasattr(operation, 'setClusterConfiguration'):
                # Step-3: begin maintenance routine.
                final_config = operation.setClusterConfiguration
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

                # Sleep before polling to give Atlas time to update cluster.stateName.
                sleep(3)

                # Step-4: wait until maintenance completes (cluster is IDLE).
                self.wait_for_idle()
                self.verify_cluster_configuration_matches(final_config)
                LOGGER.info("Cluster maintenance complete")
                
            if hasattr(operation, 'testFailover'):
                self.cluster_url['restartPrimaries'].post()
                
                self.wait_for_idle()
                
            if hasattr(operation, 'sleep'):
                _time.sleep(operation['sleep'])
                
            if hasattr(operation, 'waitForIdle'):
                self.wait_for_idle()
                
            if hasattr(operation, 'restartVms'):
                url = "/api/private/nds/groups/%s/clusters/%s/reboot" % (self.project.id, self.cluster_name)
                self.admin_client.request('POST', url)
                
                sleep(5)
                self.wait_for_idle()
                
            if hasattr(operation, 'assertPrimaryRegion'):
                region = operation['assertPrimaryRegion']
                
                cluster_config = self.cluster_url.get().data
                deadline = monotonic() + 90
                
                while True:
                    mc = MongoClient(cluster_config['connectionStrings']['standard'], username='atlasuser', password='mypassword123')
                    rsc = mc.admin.command('replSetGetConfig')
                    member = [m for m in rsc['config']['members']
                        if m['horizons']['PUBLIC'] == '%s:%s' % mc.primary][0]
                    member_region = member['tags']['region']
                    mc.close()
                    
                    if region == member_region:
                        break
                        
                    if monotonic() > deadline:
                        raise Exception("Primary in cluster not in expected region '%s' (actual region '%s')" % (region, member_region))
                    else:
                        sleep(5)
                

        # Step-5: interrupt driver workload and capture streams
        stats = self.workload_runner.terminate()

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
        
        LOGGER.info("Waiting 5 minutes for Atlas logs to become available")
        sleep(5*60)
        
        self.retrieve_logs()

        # Step 7: download logs asynchronously and delete cluster.
        # TODO: https://github.com/mongodb-labs/drivers-atlas-testing/issues/4
        if not persist_cluster:
            self.cluster_url.delete()
            LOGGER.info("Cluster {!r} marked for deletion.".format(
                self.cluster_name))

        return junit_test
        
    def wait_for_idle(self):
        selector = BooleanCallablePoller(
            frequency=self.config.polling_frequency,
            timeout=self.config.polling_timeout)
        LOGGER.info("Waiting for cluster maintenance to complete")
        selector.poll([self], attribute="is_cluster_state", args=("IDLE",),
                      kwargs={})
                      
    def retrieve_logs(self):
        # There is no straightforward facility in Atlas to retrieve logs
        # for a cluster. See https://jira.mongodb.org/browse/PRODTRIAGE-968.
        # Atlas provides the "cluster start" time, added in
        # https://jira.mongodb.org/browse/CLOUDP-73874. This is however
        # not the time when any process started, but appears to be roughly
        # the time when cluster creation began. Since a cluster can take
        # anywhere from 6 to 30 minutes to provision depending on the type,
        # simply retrieving logs from the "cluster start" time would result in
        # several of the intervals retrieving the exact same data from when
        # a process really started.
        # Because of this, figure out the times the hard way:
        # - Retrieve the first log starting with the "cluster start" time.
        # - Read the first log line.
        # - Use the time in that line as the actual node start time.
        # - Step forward in 5 minute increments to get the entire log,
        #   hopefully in a complete and correct manner. See
        #   https://jira.mongodb.org/browse/PRODTRIAGE-1030 for why
        #   using end time (or simply using the API as documented) doesn't work.
        
        end_time = _time.time()
        cluster_config = self.cluster_url.get().data
        data = self.client.request('GET', 'groups/%s/processes' % self.project.id).data
        for hostinfo in data['results']:
            hostname = hostinfo['hostname']
            
            log_names = {'mongodb.gz': 'mongod.log'}
            if cluster_config['clusterType'] == 'SHARDED':
                log_names['mongos.gz'] = 'mongos.log'
            
            for api_log_name, log_name in log_names.items():
        
                time = int(self.start_time)
                while time < end_time:
                    fn = '%s_%s_%s.gz' % (hostname, log_name, datetime.datetime.fromtimestamp(time).strftime('%Y%m%dT%H:%M:%SZ'))
                    LOGGER.info('Retrieving %s' % fn)
                    resp = self.client.request('GET', 'groups/%s/clusters/%s/logs/%s' % (self.project.id, hostname, api_log_name), startDate=time)
                    with open(fn, 'wb') as f:
                        f.write(resp.response.content)
                        
                    time += 5*60
        
    def iso8601_to_timestamp(self, time_str):
        if time_str.endswith('Z'):
            format = '%Y-%m-%dT%H:%M:%SZ'
        else:
            format = '%Y-%m-%dT%H:%M:%S.%f+0000'
        t = datetime.datetime.strptime(time_str, format)
        return int(_time.mktime(t.timetuple()))


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
                    yaml.load(spec_file, Loader=yaml.FullLoader))

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
