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

from itertools import chain
from textwrap import dedent

from tabulate import tabulate

from astrolabe.configuration import (
    CONFIG_ENVVARS as ENVVARS,
    CONFIG_DEFAULTS as DEFAULTS,
    CLI_OPTION_NAMES as OPTNAMES)
from atlasclient.configuration import CONFIG_DEFAULTS as CL_DEFAULTS


def generate_environment_variables_help():
    text = dedent("""\
    Many of Astrolabe's configuration options can be set at runtime using
    environment variables. The following table lists configurable options
    and the corresponding environment variables that can used to set them:
    {}""")
    tabledata = []
    for internal_id, envvar_name in ENVVARS.items():
        tabledata.append([internal_id, OPTNAMES[internal_id], envvar_name])
    headers = ["Internal ID", "CLI Option Name",
               "Environment Variable"]
    tabletext = tabulate(tabledata, headers=headers, tablefmt="rst")
    return text.format(tabletext)


def generate_default_value_help():
    text = "Default values of Astrolabe's configuration options are:\n{}"
    tabledata = []
    for internal_id, default_value in chain(
            CL_DEFAULTS.items(), DEFAULTS.items()):
        if internal_id in OPTNAMES:
            tabledata.append(
                [internal_id, OPTNAMES[internal_id], default_value])
    headers = ["Internal ID", "CLI Option Name", "Default Value"]
    tabletext = tabulate(tabledata, headers=headers, tablefmt="rst")
    return text.format(tabletext)


def tabulate_astrolabe_configuration(config):
    table_data = [["Atlas organization name", config.organization_name],
                  ["Atlas group/project name", config.group_name],
                  ["Salt for cluster names", config.name_salt],
                  ["Polling frequency (Hz)", config.polling_frequency],
                  ["Polling timeout (s)", config.polling_timeout]]
    table_txt = "Astrolabe Configuration:\n{}"
    return table_txt.format(tabulate(
        table_data, headers=["Configuration option", "Value"], tablefmt="rst"))


def tabulate_client_configuration(base_url, http_timeout):
    table_data = [["Atlas API base URL", base_url],
                  ["HTTP timeout (s)", http_timeout]]
    table_txt = "Atlas Client Configuration:\n{}"
    return table_txt.format(tabulate(
        table_data, headers=["Configuration option", "Value"], tablefmt="rst"))
