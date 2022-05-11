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

from textwrap import dedent

from tabulate import tabulate

from astrolabe.configuration import CONFIGURATION_OPTIONS as CONFIGOPTS


def generate_configuration_help():
    text = dedent("""\
    Astrolabe has many configurable options that can be set at runtime via the command-line, or using environment variables. The following table 
    lists these configurable options, their default values, and the environment variables that can be used to specify them. 
    Note that if an option is specified using an environment variable, and also via the command-line, the command-line value takes precedence.
    {}""")
    tabledata = []
    headers = ["CLI Option", "Environment Variable", "Default", "Description"]
    for _, optspec in CONFIGOPTS.items():
        cliopt_string = optspec['cliopt']
        if isinstance(cliopt_string, tuple):
            cliopt_string = '/'.join(cliopt_string)
        tabledata.append([
            cliopt_string, optspec.get('envvar', '-'),
            str(optspec.get('default', '-')), optspec['help']])
    tabletext = tabulate(tabledata, headers=headers, tablefmt="rst")
    return text.format(tabletext)


def tabulate_astrolabe_configuration(config):
    table_data = [["Atlas organization name", config.organization_name],
                  ["Atlas organization id", config.organization_id],
                  ["Atlas project name prefix", config.project_name],
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
