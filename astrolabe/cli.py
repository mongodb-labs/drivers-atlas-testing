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
from pprint import pprint
from urllib.parse import unquote_plus

import click

import astrolabe.commands as cmd
import astrolabe.docgen as docgen
from atlasclient import AtlasClient, AtlasApiBaseError
from atlasclient.configuration import CONFIG_DEFAULTS as CL_DEFAULTS
from astrolabe.docgen import (
    tabulate_astrolabe_configuration, tabulate_client_configuration)
from astrolabe.spec_runner import MultiTestRunner, SingleTestRunner
from astrolabe.configuration import (
    CLI_OPTION_NAMES as OPTNAMES,
    CONFIG_DEFAULTS as DEFAULTS,
    CONFIG_ENVVARS as ENVVARS,
    TestCaseConfiguration)
from astrolabe.utils import (
    get_cluster_name, get_test_name_from_spec_file, ClickLogHandler)


LOGGER = logging.getLogger(__name__)


# Define CLI options used in multiple commands for easy re-use.
DBUSERNAME_OPTION = click.option(
    OPTNAMES.DB_USERNAME, type=click.STRING, default=DEFAULTS.DB_USERNAME,
    show_default=True, help='Database username on the MongoDB instance.')

DBPASSWORD_OPTION = click.option(
    OPTNAMES.DB_PASSWORD, type=click.STRING, default=DEFAULTS.DB_PASSWORD,
    show_default=True, help='Database password on the MongoDB instance.')

ATLASORGANIZATIONNAME_OPTION = click.option(
    OPTNAMES.ORGANIZATION_NAME, type=click.STRING,
    default=DEFAULTS.ORGANIZATION_NAME, show_default=True,
    help='Name of the Atlas Organization.')

ATLASCLUSTERNAME_OPTION = click.option(
    '--cluster-name', required=True, type=click.STRING,
    help='Name of the Atlas Cluster.')

ATLASGROUPNAME_OPTION = click.option(
    OPTNAMES.PROJECT_NAME, required=True, type=click.STRING,
    envvar=ENVVARS.PROJECT_NAME, help='Name of the Atlas Project.')

POLLINGTIMEOUT_OPTION = click.option(
    OPTNAMES.POLLING_TIMEOUT, type=click.FLOAT, show_default=True,
    envvar=ENVVARS.POLLING_TIMEOUT, default=DEFAULTS.POLLING_TIMEOUT,
    help="Maximum time (in s) to poll API endpoints.")

POLLINGFREQUENCY_OPTION = click.option(
    OPTNAMES.POLLING_FREQUENCY, type=click.FLOAT, show_default=True,
    envvar=ENVVARS.POLLING_FREQUENCY, default=DEFAULTS.POLLING_FREQUENCY,
    help='Frequency (in Hz) at which to poll API endpoints.')

WORKLOADEXECUTOR_OPTION = click.option(
    '-e', '--workload-executor', required=True, type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Absolute or relative path to the workload-executor')

CLUSTERNAMESALT_OPTION = click.option(
    OPTNAMES.CLUSTER_NAME_SALT, type=click.STRING, required=True,
    envvar=ENVVARS.CLUSTER_NAME_SALT,
    help='Salt for generating unique hashes.')

XUNITOUTPUT_OPTION = click.option(
    '--xunit-output', type=click.STRING, default="xunit-output",
    help='Name of the folder in which to write the XUnit XML files.')

NODELETE_FLAG = click.option(
    '--no-delete', is_flag=True, default=False,
    help=('Flag to instructs astrolabe to not delete clusters at the end of '
          'the test run. Useful when a test will be run multiple times with '
          'the same cluster name salt.'))


@click.group()
@click.option(OPTNAMES.BASE_URL, envvar=ENVVARS.BASE_URL,
              default=CL_DEFAULTS.BASE_URL, show_default=True,
              type=click.STRING, help='Base URL of the Atlas API.')
@click.option('-u', '--atlas-api-username', required=True,
              envvar=ENVVARS.API_USERNAME, type=click.STRING,
              help='HTTP-Digest username (Atlas API public-key).')
@click.option('-p', '--atlas-api-password', required=True,
              envvar=ENVVARS.API_PASSWORD, type=click.STRING,
              help='HTTP-Digest password (Atlas API private-key).')
@click.option(OPTNAMES.HTTP_TIMEOUT, envvar=ENVVARS.HTTP_TIMEOUT,
              default=CL_DEFAULTS.HTTP_TIMEOUT, type=click.FLOAT,
              show_default=True,
              help='Time (in s) after which HTTP requests should timeout.')
@click.option('-v', OPTNAMES.LOG_VERBOSITY, envvar=ENVVARS.LOG_VERBOSITY,
              type=click.Choice(
                  ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                  case_sensitive=False), default=DEFAULTS.LOG_VERBOSITY,
              show_default=True, help='Set the logging level.')
@click.version_option()
@click.pass_context
def cli(ctx, atlas_base_url, atlas_api_username,
        atlas_api_password, http_timeout, log_level):

    """
    Astrolabe is a command-line application for running automated driver
    tests against a MongoDB Atlas cluster undergoing maintenance.
    """
    client = AtlasClient(
        base_url=atlas_base_url,
        username=atlas_api_username,
        password=atlas_api_password,
        timeout=http_timeout)
    ctx.obj = client

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
    pprint(ctx.obj.root.get().data)


@cli.group('organizations')
def atlas_organizations():
    """Commands related to Atlas Organizations."""
    pass


@atlas_organizations.command('list')
@click.pass_context
def list_all_organizations(ctx):
    """List all Atlas Organizations (limited to first 100)."""
    pprint(ctx.obj.orgs.get().data)


@atlas_organizations.command('get-one')
@ATLASORGANIZATIONNAME_OPTION
@click.pass_context
def get_one_organization_by_name(ctx, org_name):
    """Get one Atlas Organization by name. Prints "None" if no organization
    bearing the given name exists."""
    pprint(cmd.get_one_organization_by_name(
        client=ctx.obj, organization_name=org_name))


@cli.group('projects')
def atlas_projects():
    """Commands related to Atlas Projects."""
    pass


@atlas_projects.command('ensure')
@ATLASORGANIZATIONNAME_OPTION
@ATLASGROUPNAME_OPTION
@click.pass_context
def create_project_if_necessary(ctx, org_name, group_name,):
    """Ensure that the given Atlas Project exists."""
    org = cmd.get_one_organization_by_name(
        client=ctx.obj, organization_name=org_name)
    pprint(cmd.ensure_project(
        client=ctx.obj, group_name=group_name, organization_id=org.id))


@atlas_projects.command('list')
@click.pass_context
def list_projects(ctx):
    """List all Atlas Projects (limited to first 100)."""
    pprint(ctx.obj.groups.get().data)


@atlas_projects.command('get-one')
@ATLASGROUPNAME_OPTION
@click.pass_context
def get_one_project_by_name(ctx, group_name):
    """Get one Atlas Project."""
    pprint(ctx.obj.groups.byName[group_name].get().data)


@atlas_projects.command('enable-anywhere-access')
@ATLASGROUPNAME_OPTION
@click.pass_context
def enable_project_access_from_anywhere(ctx, group_name):
    """Add 0.0.0.0/0 to the IP whitelist of the Atlas Project."""
    group = ctx.obj.groups.byName[group_name].get().data
    cmd.ensure_connect_from_anywhere(client=ctx.obj, group_id=group.id)


@cli.group('users')
def atlas_users():
    """Commands related to Atlas Users."""
    pass


@atlas_users.command('create-admin-user')
@DBUSERNAME_OPTION
@DBPASSWORD_OPTION
@ATLASGROUPNAME_OPTION
@click.pass_context
def create_user(ctx, db_username, db_password, group_name):
    """Create an Atlas User with admin privileges. Modifies user
    permissions, if the user already exists."""
    group = ctx.obj.groups.byName[group_name].get().data
    user = cmd.ensure_admin_user(
        client=ctx.obj, group_id=group.id, username=db_username,
        password=db_password)
    pprint(user)


@atlas_users.command('list')
@ATLASGROUPNAME_OPTION
@click.pass_context
def list_users(ctx, group_name):
    """List all Atlas Users."""
    project = ctx.obj.groups.byName[group_name].get().data
    pprint(ctx.obj.groups[project.id].databaseUsers.get().data)


@cli.group('clusters')
def atlas_clusters():
    """Commands related to Atlas Clusters."""
    pass


@atlas_clusters.command('create-dedicated')
@ATLASGROUPNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.option('-s', '--instance-size-name', required=True,
              type=click.Choice(["M10", "M20"]),
              help="Name of AWS Cluster Tier to provision.")
@click.pass_context
def create_cluster(ctx, group_name, cluster_name, instance_size_name):
    """Create a new dedicated-tier Atlas Cluster."""
    project = ctx.obj.groups.byName[group_name].get().data

    cluster_config = {
        'name': cluster_name,
        'clusterType': 'REPLICASET',
        'providerSettings': {
            'providerName': 'AWS',
            'regionName': 'US_WEST_1',
            'instanceSizeName': instance_size_name}}

    cluster = ctx.obj.groups[project.id].clusters.post(**cluster_config)
    pprint(cluster.data)


@atlas_clusters.command('get-one')
@ATLASCLUSTERNAME_OPTION
@ATLASGROUPNAME_OPTION
@click.pass_context
def get_one_cluster_by_name(ctx, cluster_name, group_name):
    """Get one Atlas Cluster."""
    project = ctx.obj.groups.byName[group_name].get().data
    cluster = ctx.obj.groups[project.id].clusters[cluster_name].get()
    pprint(cluster.data)


@atlas_clusters.command('resize-dedicated')
@ATLASGROUPNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.option('-s', '--instance-size-name', required=True,
              type=click.Choice(["M10", "M20"]),
              help="Target AWS Cluster Tier.")
@click.pass_context
def resize_cluster(ctx, group_name, cluster_name, instance_size_name):
    """Resize an existing dedicated-tier Atlas Cluster."""
    project = ctx.obj.groups.byName[group_name].get().data

    new_cluster_config = {
        'clusterType': 'REPLICASET',
        'providerSettings': {
            'providerName': 'AWS',
            'regionName': 'US_WEST_1',
            'instanceSizeName': instance_size_name}}

    cluster = ctx.obj.groups[project.id].clusters[cluster_name].patch(
        **new_cluster_config)
    pprint(cluster.data)


@atlas_clusters.command('toggle-js')
@ATLASGROUPNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.pass_context
def toggle_cluster_javascript(ctx, group_name, cluster_name):
    """Enable/disable server-side javascript for an existing Atlas Cluster."""
    project = ctx.obj.groups.byName[group_name].get().data

    # Alias to reduce verbosity.
    pargs = ctx.obj.groups[project.id].clusters[cluster_name].processArgs

    initial_process_args = pargs.get()
    target_js_value = not initial_process_args.data.javascriptEnabled

    cluster = pargs.patch(javascriptEnabled=target_js_value)
    pprint(cluster.data)


@atlas_clusters.command('list')
@ATLASGROUPNAME_OPTION
@click.pass_context
def list_clusters(ctx, group_name):
    """List all Atlas Clusters."""
    project = ctx.obj.groups.byName[group_name].get().data
    clusters = ctx.obj.groups[project.id].clusters.get()
    pprint(clusters.data)


@atlas_clusters.command('isready')
@ATLASGROUPNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.pass_context
def isready_cluster(ctx, group_name, cluster_name):
    """Check if the Atlas Cluster is 'IDLE'."""
    project = ctx.obj.groups.byName[group_name].get().data
    state = ctx.obj.groups[project.id].clusters[cluster_name].get().data.stateName

    if state == "IDLE":
        click.echo("True")
        exit(0)
    click.echo("False", err=True)
    exit(1)


@atlas_clusters.command('delete')
@ATLASGROUPNAME_OPTION
@ATLASCLUSTERNAME_OPTION
@click.pass_context
def delete_cluster(ctx, group_name, cluster_name):
    """Delete the Atlas Cluster."""
    project = ctx.obj.groups.byName[group_name].get().data
    ctx.obj.groups[project.id].clusters[cluster_name].delete().data
    click.echo("DONE!")


@cli.group('info')
def help_topics():
    """Help topics for astrolabe users."""
    pass


@help_topics.command('environment-variables')
def help_environment_variables():
    """About configuring astrolabe via environment variables."""
    click.echo_via_pager(docgen.generate_environment_variables_help())


@help_topics.command('default-values')
def help_default_values():
    """About default values of configuration options."""
    click.echo_via_pager(docgen.generate_default_value_help())


@cli.group('spec-tests')
def spec_tests():
    """Commands related to running APM spec-tests."""
    pass


@spec_tests.command('run-one')
@click.argument("spec_test_file", type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@WORKLOADEXECUTOR_OPTION
@DBUSERNAME_OPTION
@DBPASSWORD_OPTION
@ATLASORGANIZATIONNAME_OPTION
@ATLASGROUPNAME_OPTION
@CLUSTERNAMESALT_OPTION
@POLLINGTIMEOUT_OPTION
@POLLINGFREQUENCY_OPTION
@XUNITOUTPUT_OPTION
@NODELETE_FLAG
@click.pass_context
def run_single_test(ctx, spec_test_file, workload_executor,
                    db_username, db_password, org_name, group_name,
                    cluster_name_salt, polling_timeout, polling_frequency,
                    xunit_output, no_delete):
    """
    Run one APM test.
    This command runs the test found in the SPEC_TEST_FILE.
    """
    # Step-0: construct test configuration object and log configuration.
    config = TestCaseConfiguration(
        organization_name=org_name,
        group_name=group_name,
        name_salt=cluster_name_salt,
        polling_timeout=polling_timeout,
        polling_frequency=polling_frequency,
        database_username=unquote_plus(db_username),
        database_password=unquote_plus(db_password),
        workload_executor=workload_executor)
    LOGGER.info(tabulate_astrolabe_configuration(config))

    # Step-1: create the Test-Runner.
    runner = SingleTestRunner(client=ctx.obj,
                              test_locator_token=spec_test_file,
                              configuration=config,
                              xunit_output=xunit_output,
                              persist_clusters=no_delete)

    # Step-2: run the tests.
    failed = runner.run()

    if failed:
        exit(1)
    else:
        exit(0)


@spec_tests.command('delete-cluster')
@click.argument("spec_test_file", type=click.Path(
    exists=True, file_okay=True, dir_okay=False, resolve_path=True))
@ATLASORGANIZATIONNAME_OPTION
@ATLASGROUPNAME_OPTION
@CLUSTERNAMESALT_OPTION
@click.pass_context
def delete_test_cluster(ctx, spec_test_file, org_name, group_name,
                        cluster_name_salt):
    """
    Deletes the cluster used by the APM test in the SPEC_TEST_FILE.

    This command does not error if no cluster by the give name is found.
    """
    # Step-1: determine the cluster name for the given test.
    cluster_name = get_cluster_name(get_test_name_from_spec_file(
        spec_test_file), cluster_name_salt)

    # Step-2: delete the cluster.
    organization = cmd.get_one_organization_by_name(
        client=ctx.obj, organization_name=org_name)
    group = cmd.ensure_project(
        client=ctx.obj, group_name=group_name, organization_id=organization.id)
    try:
        ctx.obj.groups[group.id].clusters[cluster_name].delete()
    except AtlasApiBaseError:
        pass


@spec_tests.command('run')
@click.argument("spec_tests_directory", type=click.Path(
    exists=True, file_okay=False, dir_okay=True, resolve_path=True))
@WORKLOADEXECUTOR_OPTION
@DBUSERNAME_OPTION
@DBPASSWORD_OPTION
@ATLASORGANIZATIONNAME_OPTION
@ATLASGROUPNAME_OPTION
@CLUSTERNAMESALT_OPTION
@POLLINGTIMEOUT_OPTION
@POLLINGFREQUENCY_OPTION
@XUNITOUTPUT_OPTION
@NODELETE_FLAG
@click.pass_context
def run_headless(ctx, spec_tests_directory, workload_executor, db_username,
                 db_password, org_name, group_name, cluster_name_salt,
                 polling_timeout, polling_frequency, xunit_output, no_delete):
    """
    Main entry point for running APM tests in headless environments.
    This command runs all tests found in the SPEC_TESTS_DIRECTORY
    sequentially on an Atlas cluster.
    """
    # Step-0: construct test configuration object and log configuration.
    config = TestCaseConfiguration(
        organization_name=org_name,
        group_name=group_name,
        name_salt=cluster_name_salt,
        polling_timeout=polling_timeout,
        polling_frequency=polling_frequency,
        database_username=unquote_plus(db_username),
        database_password=unquote_plus(db_password),
        workload_executor=workload_executor)
    LOGGER.info(tabulate_astrolabe_configuration(config))

    # Step-1: create the Test-Runner.
    runner = MultiTestRunner(client=ctx.obj,
                             test_locator_token=spec_tests_directory,
                             configuration=config,
                             xunit_output=xunit_output,
                             persist_clusters=no_delete)

    # Step-2: run the tests.
    failed = runner.run()

    if failed:
        exit(1)
    else:
        exit(0)


if __name__ == '__main__':
    cli()
