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

from collections import defaultdict
import logging
import json

from atlasclient import AtlasApiError


LOGGER = logging.getLogger(__name__)


def get_organization_by_id(*, client, org_id):
    """Get the organization by the given id `org_id`."""
    org = client.orgs[org_id].get().data 
    LOGGER.debug("Organization details: {}".format(org))   
    return org    


def get_project(*, client, project_name, organization_id):
    """Returns project with specified name if one exists, otherwise None."""
    try:
        project = client.groups.byName[project_name].get().data
    except AtlasApiError as exc:
        if exc.error_code == 'MULTIPLE_GROUPS':
            LOGGER.warn("There are many projects {!r}".format(project_name))
            projects_res = client.orgs[organization_id].groups.get().data
            project = projects_res['results'][0]
        else:
            raise
    LOGGER.debug("Project details: {}".format(project))
    return project


def ensure_project(*, client, project_name, organization_id):
    """Ensure a project named `project_name` exists and return it. Does not
    raise an exception if a project by that name already exists."""
    try:
        project = client.groups.post(
            name=project_name, orgId=organization_id).data
    except AtlasApiError as exc:
        if exc.error_code == 'GROUP_ALREADY_EXISTS':
            LOGGER.debug("Project {!r} already exists".format(project_name))
            project = get_project(client=client, project_name=project_name, organization_id=organization_id)
        else:
            raise
    else:
        LOGGER.debug("Project {!r} successfully created".format(project.name))

    LOGGER.debug("Project details: {}".format(project))
    return project


def list_projects_in_org(*, client, org_id):
    """List all projects inside organization with id `org_id`."""
    projects_res = client.orgs[org_id].groups.get(
            itemsPerPage=500).data
    LOGGER.debug("Retrieved {} projects in org id: {}".format(projects_res.totalCount, org_id))
    return projects_res


def delete_project(*, client, project_id):
    """Delete a project with id `project_id`"""    
    
    clusters = client.groups[project_id].clusters.get()
    for cluster in clusters.data['results']:
        LOGGER.debug("Deleting cluster {}".format(cluster['name']))
        try:
            client.groups[project_id].clusters[cluster['name']].delete().data
        except AtlasApiError as exc:
            # May already have been requested to be deleted earlier but still
            # not deleted, atlas returns an error in this case
            LOGGER.warn(exc)
    
    try:
        client.groups[project_id].delete().data
        LOGGER.debug("Deleted project id: {}".format(project_id))
    except AtlasApiError as exc:
        # Some clusters may remain pending deletion, which prevents
        # deleting the project
        LOGGER.warn(exc)

def ensure_admin_user(*, client, project_id, username, password):
    """Ensure an admin user with the given credentials exists on the project
    bearing ID `project_id`. Updates credentials and returns if a user bearing
    name `username` already exists, """
    user_details = {
        "groupId": project_id,
        "databaseName": "admin",
        "roles": [{
            "databaseName": "admin",
            "roleName": "atlasAdmin"}],
        "username": username,
        "password": password}

    try:
        user = client.groups[project_id].databaseUsers.post(**user_details).data
    except AtlasApiError as exc:
        if exc.error_code == "USER_ALREADY_EXISTS":
            LOGGER.debug("User {!r} already exists".format(username))
            username = user_details.pop("username")
            user = client.groups[project_id].databaseUsers.admin[username].patch(
                **user_details).data
        else:
            raise
    else:
        LOGGER.debug("User {!r} successfully created".format(username))

    LOGGER.debug("User details: {}".format(user))
    return user


def ensure_connect_from_anywhere(*, client, project_id, ):
    """Add the 0.0.0.0/0 CIDR block to the IP whitelist of the specified
    Atlas project."""
    ip_details_list = [{"cidrBlock": "0.0.0.0/0"}]
    resp = client.groups[project_id].whitelist.post(json=ip_details_list).data
    LOGGER.debug("Project whitelist details: {}".format(resp))


def aggregate_statistics():
    '''Read the results.json and events.json files, aggregate the events into
    statistics and write the statistics into stats.json.
    
    Statistics calculated:
    
    - Average command execution time
    - 95th percentile command execution time
    - 99th percentile command execution time
    - Peak number of open connections
    '''
    
    with open('results.json', 'r') as fp:
        stats = json.load(fp)
    with open('events.json', 'r') as fp:
        events = json.load(fp)
    
    import numpy
    
    command_events = [
        event for event in events['events']
        if event['name'].startswith('Command')
    ]
    map = {}
    correlated_events = []
    for event in command_events:
        if event['name'] == 'CommandStartedEvent':
            map[event['requestId']] = event
        else:
            started_event = map[event['requestId']]
            del map[event['requestId']]
            _event = dict(started_event)
            _event.update(event)
            correlated_events.append(_event)
    command_times = [c['duration'] for c in correlated_events]
    stats['avgCommandTime'] = numpy.average(command_times)
    stats['p95CommandTime'] = numpy.percentile(command_times, 95)
    stats['p99CommandTime'] = numpy.percentile(command_times, 99)
    
    conn_events = [
        event for event in events['events']
        if event['name'].startswith('Connection') or event['name'].startswith('Pool')
    ]
    counts = defaultdict(lambda: 0)
    max_counts = defaultdict(lambda: 0)
    conn_count = max_conn_count = 0
    for e in conn_events:
        if e['name'] == 'ConnectionCreatedEvent':
            counts[e['address']] += 1
        elif e['name'] == 'ConnectionClosedEvent':
            counts[e['address']] -= 1
        if counts[e['address']] > max_counts[e['address']]:
            max_counts[e['address']] = counts[e['address']]
    
    stats['maxConnectionCounts'] = max_counts
    
    with open('stats.json', 'w') as fp:
        json.dump(stats, fp)
