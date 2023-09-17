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
import unittest
from pprint import pprint
from urllib.parse import unquote_plus

import click
from atlasclient import AtlasApiBaseError, AtlasApiError, AtlasClient
from atlasclient.exceptions import AtlasClientError

import astrolabe.commands as cmd
from astrolabe.atlas_runner import MultiTestRunner, SingleTestRunner
from astrolabe.configuration import CONFIGURATION_OPTIONS as CONFIGOPTS
from astrolabe.configuration import TestCaseConfiguration
from astrolabe.docgen import (generate_configuration_help,
                              tabulate_astrolabe_configuration,
                              tabulate_client_configuration)
from astrolabe.exceptions import PollingTimeoutError
from astrolabe.kubernetes_runner import KubernetesTest
from astrolabe.utils import (ClickLogHandler, SingleTestXUnitLogger,
                             create_click_option, get_cluster_name, get_logs,
                             get_test_name,
                             require_requests_ipv4)
from astrolabe.validator import validator_factory

LOGGER = logging.getLogger(__name__)

DBUSERNAME_OPTION = create_click_option(CONFIGOPTS.ATLAS_DB_USERNAME)

DBPASSWORD_OPTION = create_click_option(CONFIGOPTS.ATLAS_DB_PASSWORD)

ATLASORGANIZATIONNAME_OPTION = create_click_option(
    CONFIGOPTS.ATLAS_ORGANIZATION_NAME)

ATLASORGANIZATIONID_OPTION = create_click_option(
    CONFIGOPTS.ATLAS_ORGANIZATION_ID)

ATLASPROJECTNAME_OPTION = create_click_option(CONFIGOPTS.ATLAS_PROJECT_NAME)

POLLINGTIMEOUT_OPTION = create_click_option(CONFIGOPTS.ATLAS_POLLING_TIMEOUT)

POLLINGFREQUENCY_OPTION = create_click_option(
    CONFIGOPTS.ATLAS_POLLING_FREQUENCY)

EXECUTORSTARTUPTIME_OPTION = create_click_option(
    CONFIGOPTS.ASTROLABE_EXECUTOR_STARTUP_TIME)

CLUSTERNAMESALT_OPTION = create_click_option(CONFIGOPTS.CLUSTER_NAME_SALT)

ATLASCLUSTERNAME_OPTION = click.option(
    '--cluster-name', required=True, type=click.STRING,
    help='Name of the Atlas Cluster.')

WORKLOADEXECUTOR_OPTION = click.option(
    '-e', '--workload-executor', required=True, type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Absolute or relative path to the workload-executor.')

WORKLOAD_FILE_OPTION = click.option(
    '--workload-file',
    help='Path to the unified test format workload file.',
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    required=True)

XUNITOUTPUT_OPTION = click.option(
    '--xunit-output', type=click.STRING, default="xunit-output",
    show_default=True,
    help='Name of the folder in which to write the XUnit XML files.')

NODELETE_FLAG = click.option(
    '--no-delete', is_flag=True, default=False,
    help=('Flag to instructs astrolabe to not delete clusters at the end of '
          'the test run. Useful when a test will be run multiple times with '
          'the same cluster name salt.'))

NOCREATE_FLAG = click.option(
    '--no-create', is_flag=True, default=False,
    help=('Do not create and configure clusters at the beginning of the run '
        'if they already exist, assume they have already been provisioned by '
        'a previous run.'))

ONLYONFAILURE_FLAG = click.option(
    '--only-on-failure', is_flag=True, default=False,
    help=('Only retrieve logs if the test run failed.'))

CONNECTION_STRING_OPTION = click.option(
    '--connection-string',
    help='Database connection string.',
    type=click.STRING,
    required=True,
    prompt=True)

class ContextStore:
    def __init__(self, client, admin_client):
        self.client = client
        self.admin_client = admin_client


@click.group(context_settings = dict(help_option_names=['-h', '--help']))
@create_click_option(CONFIGOPTS.ATLAS_API_BASE_URL)
@create_click_option(CONFIGOPTS.ATLAS_API_USERNAME)
@create_click_option(CONFIGOPTS.ATLAS_API_PASSWORD)
@create_click_option(CONFIGOPTS.ATLAS_ADMIN_API_USERNAME)
@create_click_option(CONFIGOPTS.ATLAS_ADMIN_API_PASSWORD)
@create_click_option(CONFIGOPTS.ATLAS_HTTP_TIMEOUT)
@create_click_option(CONFIGOPTS.ASTROLABE_LOGLEVEL)
@click.version_option()
@click.pass_context
def cli(ctx, atlas_base_url, atlas_api_username,
        atlas_api_password, atlas_admin_api_username, atlas_admin_api_password,
        http_timeout, log_level):

    """
    Astrolabe is a command-line application for running automated driver
    tests against a MongoDB Atlas cluster undergoing maintenance.
    """
    # Create an atlasclient and attach it to the context.
    client = AtlasClient(
        base_url=atlas_base_url,
        username=atlas_api_username,
        password=atlas_api_password,
        timeout=http_timeout)

    if atlas_admin_api_username:
        admin_client = AtlasClient(
            base_url=atlas_base_url,
            username=atlas_admin_api_username,
            password=atlas_admin_api_password,
            timeout=http_timeout)
    else:
        admin_client = None

    ctx.obj = ContextStore(client, admin_client)

    # Configure logging.
    loglevel = getattr(logging, log_level.upper())
    logging.basicConfig(
        level=loglevel, handlers=[ClickLogHandler()],
        format="%(levelname)s:%(name)s:%(message)s")

    # Log atlasclient config.
    LOGGER.debug(tabulate_client_configuration(
        atlas_base_url, http_timeout))

    # Turn off noisy urllib3 logging.
    if loglevel == logging.DEBUG:
        logging.getLogger('urllib3').setLevel(logging.INFO)


@cli.command()
@click.pass_context
def check_connection(ctx):
    """Command to verify validity of Atlas API credentials."""
    pprint(ctx.obj.client.root.get().data)
    if ctx.obj.admin_client:
        pprint(ctx.obj.admin_client.root.get().data)


@cli.group('organizations')
def atlas_organizations():
    """Commands related to Atlas Organizations."""
    pass


@atlas_organizations.command('list')
@click.pass_context
def list_all_organizations(ctx):
    """List all Atlas Organizations (limited to first 100)."""
    pprint(ctx.obj.client.orgs.get().data)


@atlas_organizations.command('get-one')
@ATLASORGANIZATIONID_OPTION
@click.pass_context
def get_organization_by_id(ctx, org_id):
    """Get Atlas Organization by id. Prints "None" if no organization exists.
    """
    pprint(cmd.get_organization_by_id(
        client=ctx.obj.client, org_id=org_id))


@cli.group('projects')
def atlas_projects():
    """Commands related to Atlas Projects."""
    pass


@atlas_projects.command('ensure')
@ATLASORGANIZATIONID_OPTION
@ATLASPROJECTNAME_OPTION
@click.pass_context
def create_project_if_necessary(ctx, org_id, project_name, ):
    """Ensure that the given Atlas Project exists."""
    org = cmd.get_organization_by_id(
        client=ctx.obj.client, org_id=org_id)
    pprint(cmd.ensure_project(
        client=ctx.obj.client, project_name=project_name, organization_id=org.id))


@atlas_projects.command('list')
@click.pass_context
def list_projects(ctx):
    """List all Atlas Projects (limited to first 100)."""
    pprint(ctx.obj.client.groups.get().data)


@atlas_projects.command('delete-all')
@ATLASORGANIZATIONID_OPTION
@click.pass_context
def delete_all_projects(ctx, org_id):
    """Delete all Atlas Projects in organization."""
    projects_res = cmd.list_projects_in_org(client=ctx.obj.client, org_id=org_id)
    for project in projects_res['results']:
        cmd.delete_project(client=ctx.obj.client, project_id=project.id)
        LOGGER.info("Successfully deleted project {!r}, id: {!r}".format(project.name, project.id))


@atlas_projects.command('get-one')
@ATLASPROJECTNAME_OPTION
@click.pass_context
def get_one_project_by_name(ctx, project_name):
    """Get one Atlas Project."""
    pprint(ctx.obj.client.groups.byName[project_name].get().data)


@atlas_projects.command('enable-anywhere-access')
@ATLASPROJECTNAME_OPTION
@click.pass_context
def enable_project_access_from_anywhere(ctx, project_name):
    """Add 0.0.0.0/0 to the IP whitelist of the Atlas Project."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    cmd.ensure_connect_from_anywhere(client=ctx.obj.client, project_id=project.id)


@cli.group('users')
def atlas_users():
    """Commands related to Atlas Users."""
    pass


@atlas_users.command('create-admin-user')
@DBUSERNAME_OPTION
@DBPASSWORD_OPTION
@ATLASPROJECTNAME_OPTION
@click.pass_context
def create_user(ctx, db_username, db_password, project_name):
    """Create an Atlas User with admin privileges. Modifies user
    permissions, if the user already exists."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    user = cmd.ensure_admin_user(
        client=ctx.obj.client, project_id=project.id, username=db_username,
        password=db_password)
    pprint(user)


@atlas_users.command('list')
@ATLASPROJECTNAME_OPTION
@click.pass_context
def list_users(ctx, project_name):
    """List all Atlas Users."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    pprint(ctx.obj.client.groups[project.id].databaseUsers.get().data)


@cli.group('clusters')
def atlas_clusters():
    """Commands related to Atlas Clusters."""
    pass


@atlas_clusters.command('create-dedicated')
@ATLASPROJECTNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.option('-s', '--instance-size-name', required=True,
              type=click.Choice(["M10", "M20"]),
              help="Name of AWS Cluster Tier to provision.")
@click.pass_context
def create_cluster(ctx, project_name, cluster_name, instance_size_name):
    """Create a new dedicated-tier Atlas Cluster."""
    project = ctx.obj.client.groups.byName[project_name].get().data

    cluster_config = {
        'name': cluster_name,
        'clusterType': 'REPLICASET',
        'providerSettings': {
            'providerName': 'AWS',
            'regionName': 'US_WEST_1',
            'instanceSizeName': instance_size_name}}

    cluster = ctx.obj.client.groups[project.id].clusters.post(**cluster_config)
    pprint(cluster.data)


@atlas_clusters.command('get-one')
@ATLASCLUSTERNAME_OPTION
@ATLASPROJECTNAME_OPTION
@click.pass_context
def get_one_cluster_by_name(ctx, cluster_name, project_name):
    """Get one Atlas Cluster."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    cluster = ctx.obj.client.groups[project.id].clusters[cluster_name].get()
    pprint(cluster.data)


@atlas_clusters.command('resize-dedicated')
@ATLASPROJECTNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.option('-s', '--instance-size-name', required=True,
              type=click.Choice(["M10", "M20"]),
              help="Target AWS Cluster Tier.")
@click.pass_context
def resize_cluster(ctx, project_name, cluster_name, instance_size_name):
    """Resize an existing dedicated-tier Atlas Cluster."""
    project = ctx.obj.client.groups.byName[project_name].get().data

    new_cluster_config = {
        'clusterType': 'REPLICASET',
        'providerSettings': {
            'providerName': 'AWS',
            'regionName': 'US_WEST_1',
            'instanceSizeName': instance_size_name}}

    cluster = ctx.obj.client.groups[project.id].clusters[cluster_name].patch(
        **new_cluster_config)
    pprint(cluster.data)


@atlas_clusters.command('toggle-js')
@ATLASPROJECTNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.pass_context
def toggle_cluster_javascript(ctx, project_name, cluster_name):
    """Enable/disable server-side javascript for an existing Atlas Cluster."""
    project = ctx.obj.client.groups.byName[project_name].get().data

    # Alias to reduce verbosity.
    pargs = ctx.obj.client.groups[project.id].clusters[cluster_name].processArgs

    initial_process_args = pargs.get()
    target_js_value = not initial_process_args.data.javascriptEnabled

    cluster = pargs.patch(javascriptEnabled=target_js_value)
    pprint(cluster.data)


@atlas_clusters.command('list')
@ATLASPROJECTNAME_OPTION
@click.pass_context
def list_clusters(ctx, project_name):
    """List all Atlas Clusters."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    clusters = ctx.obj.client.groups[project.id].clusters.get()
    pprint(clusters.data)


@atlas_clusters.command('isready')
@ATLASPROJECTNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.pass_context
def isready_cluster(ctx, project_name, cluster_name):
    """Check if the Atlas Cluster is 'IDLE'."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    state = ctx.obj.client.groups[project.id].clusters[cluster_name].get().data.stateName

    if state == "IDLE":
        click.echo("True")
        exit(0)
    click.echo("False", err=True)
    exit(1)


@atlas_clusters.command('delete')
@ATLASPROJECTNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.pass_context
def delete_cluster(ctx, project_name, cluster_name):
    """Delete the Atlas Cluster."""
    project = ctx.obj.client.groups.byName[project_name].get().data
    ctx.obj.client.groups[project.id].clusters[cluster_name].delete().data
    click.echo("DONE!")


@atlas_clusters.command('delete-all')
@ATLASPROJECTNAME_OPTION
@click.pass_context
def delete_all_clusters(ctx, project_name):
    """Delete all Atlas Clusters in the given Atlas Project."""
    click.confirm("This will delete all clusters under the project {}. "
                  "Do you want to continue?".format(project_name), abort=True)
    project = ctx.obj.client.groups.byName[project_name].get().data
    clusters = ctx.obj.client.groups[project.id].clusters.get()
    for cluster in clusters.data['results']:
        click.echo("Deleting cluster {}".format(cluster['name']))
        ctx.obj.client.groups[project.id].clusters[cluster['name']].delete().data
    click.echo("DONE!")


@cli.group('info')
def help_topics():
    """Help topics for astrolabe users."""
    pass


@help_topics.command('configuration')
def help_configuration_options():
    """About astrolabe's configurable settings."""
    click.echo_via_pager(generate_configuration_help())

@cli.group('validate')
def validate():
    """Commands for validating test components"""
    pass

@validate.command('workload-executor')
@WORKLOADEXECUTOR_OPTION
@EXECUTORSTARTUPTIME_OPTION
@CONNECTION_STRING_OPTION
def validate_workload_executor(workload_executor, startup_time,
                               connection_string):
    """
    Runs a series of tests to validate a workload executor.
    Relies upon a user-provisioned instance of MongoDB to run operations against.
    """
    test_case_class = validator_factory(
        workload_executor, connection_string, startup_time)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_case_class)
    result = unittest.TextTestRunner(descriptions=True, verbosity=2).run(suite)
    if any([result.errors, result.failures]):
        exit(1)


@cli.group('atlas-tests')
def atlas_tests():
    """Commands related to running APM spec tests."""
    pass


@atlas_tests.command('run-one')
@click.argument("spec_test_file", type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@WORKLOAD_FILE_OPTION
@WORKLOADEXECUTOR_OPTION
@DBUSERNAME_OPTION
@DBPASSWORD_OPTION
@ATLASORGANIZATIONNAME_OPTION
@ATLASORGANIZATIONID_OPTION
@ATLASPROJECTNAME_OPTION
@CLUSTERNAMESALT_OPTION
@POLLINGTIMEOUT_OPTION
@POLLINGFREQUENCY_OPTION
@XUNITOUTPUT_OPTION
@NODELETE_FLAG
@NOCREATE_FLAG
@EXECUTORSTARTUPTIME_OPTION
@click.pass_context
def run_atlas_test(ctx, spec_test_file, workload_file, workload_executor,
                    db_username, db_password, org_name, org_id, project_name,
                    cluster_name_salt, polling_timeout, polling_frequency,
                    xunit_output, no_delete, no_create, startup_time):
    """
    Runs one APM test.
    This is the main entry point for running APM tests in headless environments.
    This command runs the test scenario from the spec test file and the driver
    workload from the workload file.
    """
    # Step-0: construct test configuration object and log configuration.
    config = TestCaseConfiguration(
        organization_name=org_name,
        organization_id=org_id,
        project_name=project_name,
        name_salt=cluster_name_salt,
        polling_timeout=polling_timeout,
        polling_frequency=polling_frequency,
        database_username=unquote_plus(db_username),
        database_password=unquote_plus(db_password),
        workload_executor=workload_executor)
    LOGGER.info(tabulate_astrolabe_configuration(config))

    if os.path.exists('status'):
        os.unlink('status')

    # Initialize the test runner. The test runner constructor performs a bunch of the Atlas setup
    # and can raise exceptions due to Atlas cluster provisioning problems. Treat any exception that
    # happens while initializing the test runner as a "cloud-failure" and not a driver failure.
    try:
        runner = SingleTestRunner(
            client=ctx.obj.client,
            admin_client=ctx.obj.admin_client,
            test_locator_token=spec_test_file,
            workload_file=workload_file,
            configuration=config,
            xunit_output=xunit_output,
            persist_clusters=no_delete,
            no_create=no_create,
            workload_startup_time=startup_time,
        )
    except Exception as exc:
        with open('status', 'w') as fp:
            fp.write('cloud-failure')
        raise

    # Run the test. The test runner can raise exceptions due to both Atlas cluster provisioning
    # problems and due to driver failures. Treat specific exceptions that happen while running the
    # test as a "cloud-failure" and all other exceptions as a driver failure.
    try:
        failed = runner.run()
    except (PollingTimeoutError, AtlasApiError):
        with open('status', 'w') as fp:
            fp.write('cloud-failure')
        raise
    except AtlasClientError as exc:
        # Intermittent atlas problem, see DRIVERS-2012.
        if 'Max retries exceeded' in str(exc):
            with open('status', 'w') as fp:
                fp.write('cloud-failure')
        raise

    if failed:
        with open('status', 'w') as fp:
            fp.write('failure')
        exit(1)
    else:
        with open('status', 'w') as fp:
            fp.write('success')
        exit(0)


@atlas_tests.command('get-logs')
@click.argument("spec_test_file", type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@WORKLOAD_FILE_OPTION
@ATLASORGANIZATIONID_OPTION
@ATLASPROJECTNAME_OPTION
@CLUSTERNAMESALT_OPTION
@POLLINGTIMEOUT_OPTION
@POLLINGFREQUENCY_OPTION
@ONLYONFAILURE_FLAG
@click.pass_context
def get_logs_cmd(ctx, spec_test_file, workload_file, org_id, project_name,
                    cluster_name_salt, polling_timeout, polling_frequency,
                    only_on_failure,
                    ):
    """
    Retrieves logs for the cluster and saves them in logs.tar.gz in the
    current working directory.
    """

    if only_on_failure:
        if os.path.exists('status'):
            with open('status') as fp:
                status = fp.read().strip()
                if status == 'success':
                    LOGGER.info('Test run status is %s, not retrieving logs' % status)
                    return
        else:
            LOGGER.info('Test run status is missing')
            # Retrieve logs because tests may have timed out

    # Step-1: determine the cluster name for the given test.
    cluster_name = get_cluster_name(
        get_test_name(spec_test_file, workload_file),
        cluster_name_salt)

    organization = cmd.get_organization_by_id(
        client=ctx.obj.client,
        org_id=org_id)
    project = cmd.ensure_project(
        client=ctx.obj.client, project_name=project_name,
        organization_id=organization.id)
    get_logs(admin_client=ctx.obj.admin_client,
        project=project, cluster_name=cluster_name)


@atlas_tests.command('delete-cluster')
@click.argument("spec_test_file", type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@WORKLOAD_FILE_OPTION
@ATLASORGANIZATIONID_OPTION
@ATLASPROJECTNAME_OPTION
@CLUSTERNAMESALT_OPTION
@click.pass_context
def delete_test_cluster(ctx, spec_test_file, workload_file, org_id, project_name,
                        cluster_name_salt):
    """
    Deletes the cluster used by the APM test.
    Deletes the cluster corresponding to the test found in the SPEC_TEST_FILE.
    This command does not error if a cluster bearing the expected name is not found.
    """
    # Step-1: determine the cluster name for the given test.
    print("\n\n\nHELLO THERE")
    print(f"{spec_test_file=}, {workload_file=}, {cluster_name_salt=}")
    cluster_name = get_cluster_name(
        get_test_name(spec_test_file, workload_file),
        cluster_name_salt)
    print(f"{cluster_name=}")
    # Step-2: delete the cluster.
    organization = cmd.get_organization_by_id(
        client=ctx.obj.client, org_id=org_id)
    project = cmd.get_project(
        client=ctx.obj.client, project_name=project_name, organization_id=organization.id)
    print(f"{project=}")
    if project:
        print("trying to delete")
        try:
            ctx.obj.client.groups[project.id].clusters[cluster_name].delete()
            print("deleted!")
        except AtlasApiBaseError as e:
            print("failed", e)
            sys.exit(1)
    else:
        print('project not found!')
        import sys
        sys.exit(1)


@atlas_tests.command('run')
@click.argument("spec_tests_directory", type=click.Path(
    exists=True, file_okay=False, dir_okay=True, resolve_path=True))
@WORKLOADEXECUTOR_OPTION
@DBUSERNAME_OPTION
@DBPASSWORD_OPTION
@ATLASORGANIZATIONNAME_OPTION
@ATLASORGANIZATIONID_OPTION
@ATLASPROJECTNAME_OPTION
@CLUSTERNAMESALT_OPTION
@POLLINGTIMEOUT_OPTION
@POLLINGFREQUENCY_OPTION
@XUNITOUTPUT_OPTION
@NODELETE_FLAG
@EXECUTORSTARTUPTIME_OPTION
@click.pass_context
def run_headless(ctx, spec_tests_directory, workload_executor, db_username,
                 db_password, org_name, org_id, project_name, cluster_name_salt,
                 polling_timeout, polling_frequency, xunit_output, no_delete,
                 startup_time):
    """
    Run multiple APM tests in serial.
    This command runs all tests found in the SPEC_TESTS_DIRECTORY sequentially
    on an Atlas cluster.
    """
    # Step-0: construct test configuration object and log configuration.
    config = TestCaseConfiguration(
        organization_name=org_name,
        organization_id=org_id,
        project_name=project_name,
        name_salt=cluster_name_salt,
        polling_timeout=polling_timeout,
        polling_frequency=polling_frequency,
        database_username=unquote_plus(db_username),
        database_password=unquote_plus(db_password),
        workload_executor=workload_executor)
    LOGGER.info(tabulate_astrolabe_configuration(config))

    # Step-1: create the Test-Runner.
    runner = MultiTestRunner(client=ctx.obj.client,
                             test_locator_token=spec_tests_directory,
                             configuration=config,
                             xunit_output=xunit_output,
                             persist_clusters=no_delete,
                             workload_startup_time=startup_time)

    # Step-2: run the tests.
    failed = runner.run()

    if failed:
        exit(1)
    else:
        exit(0)


@atlas_tests.command()
@click.pass_context
def stats(ctx):
    cmd.aggregate_statistics()

@cli.group('kubernetes-tests')
def kubernetes_tests():
    """Commands related to running Kubernetes spec tests."""
    pass


@kubernetes_tests.command('run-one')
@click.argument(
    "spec_test_file",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@WORKLOAD_FILE_OPTION
@WORKLOADEXECUTOR_OPTION
@CONNECTION_STRING_OPTION
@XUNITOUTPUT_OPTION
def run_kubernetes_test(
    spec_test_file,
    workload_file,
    workload_executor,
    connection_string,
    xunit_output):
    """
    Runs one Kubernetes test.
    """
    LOGGER.info(f"Running test {spec_test_file}, workload {workload_file}, driver {workload_executor}")

    # The test name is "{spec test filename}-{workload filename}".
    name = get_test_name(spec_test_file, workload_file)
    test = KubernetesTest(
        name=name,
        spec_test_file=spec_test_file,
        workload_file=workload_file,
        workload_executor=workload_executor,
        connection_string=connection_string)
    xunit_test = test.run()

    xunit_logger = SingleTestXUnitLogger(output_directory=xunit_output)
    xunit_logger.write_xml(
        test_case=xunit_test,
        filename=name)

    LOGGER.info("Done!")


@cli.command('check-cloud-failure')
@click.pass_context
def check_cloud_failure(ctx):
    if os.path.exists('status'):
        with open('status') as fp:
            status = fp.read().strip()
            LOGGER.info('Test status: %s' % status)
            if status == 'cloud-failure':
                LOGGER.info('Cloud failure, exiting with 1')
                exit(1)
        LOGGER.info('Not a cloud failure, exiting with 0')
    else:
        LOGGER.info('Test status file missing, exiting with 0')


@cli.command('check-success')
@click.pass_context
def check_success(ctx):
    if os.path.exists('status'):
        with open('status') as fp:
            status = fp.read().strip()
            LOGGER.info('Test status: %s' % status)
            if status == 'success':
                LOGGER.info('Success, exiting with 0')
                exit(0)
            LOGGER.info('Not a success, exiting with 1')
    else:
        LOGGER.info('Test status file missing, exiting with 1')
    exit(1)


if __name__ == '__main__':
    require_requests_ipv4()
    cli()
