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
import json

from atlasclient import AtlasApiError


LOGGER = logging.getLogger(__name__)


def get_one_organization_by_name(*, client, organization_name):
    """Get the ID of the organization by the given name. Raises
    AtlasApiError if no organization exists by the given name."""
    all_orgs = client.orgs.get().data
    for org in all_orgs.results:
        if org.name == organization_name:
            LOGGER.debug("Organization details: {}".format(org))
            return org

    raise AtlasApiError('Organization {!r} not found.'.format(
        organization_name))


def ensure_project(*, client, project_name, organization_id):
    """Ensure a project named `project_name` exists and return it. Does not
    raise an exception if a project by that name already exists."""
    try:
        project = client.groups.post(
            name=project_name, orgId=organization_id).data
    except AtlasApiError as exc:
        if exc.error_code == 'GROUP_ALREADY_EXISTS':
            LOGGER.debug("Project {!r} already exists".format(project_name))
            project = client.groups.byName[project_name].get().data
        else:
            raise
    else:
        LOGGER.debug("Project {!r} successfully created".format(project.name))

    LOGGER.debug("Project details: {}".format(project))
    return project


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
    
    command_events = events['commands']
    command_times = [c['duration'] for c in command_events]
    stats['avgCommandTime'] = numpy.average(command_times)
    stats['p95CommandTime'] = numpy.percentile(command_times, 95)
    stats['p99CommandTime'] = numpy.percentile(command_times, 99)
    
    conn_events = events['connections']
    counts = defaultdict(lambda: 0)
    max_counts = defaultdict(lambda: 0)
    conn_count = max_conn_count = 0
    for e in conn_events:
        if e['name'] == 'ConnectionCreated':
            counts[e['address']] += 1
        elif e['name'] == 'ConnectionClosed':
            counts[e['address']] -= 1
        if counts[e['address']] > max_counts[e['address']]:
            max_counts[e['address']] = counts[e['address']]
    
    stats['maxConnectionCounts'] = max_counts
    
    with open('stats.json', 'w') as fp:
        json.dump(stats, fp)
