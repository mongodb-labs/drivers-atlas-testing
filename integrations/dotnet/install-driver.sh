#!/usr/bin/env bash
set -o xtrace   # Write all commands first to stderr
set -o errexit  # Exit the script with error if any of the commands fail

# Environment variables used as input:
#   FRAMEWORK                       Set to specify .NET framework to test against. Values: "netcoreapp2.1"

# temporary workaround until https://jira.mongodb.org/browse/BUILD-14126 is resolved
# the below .ps1 script install .net50 into ${LOCALAPPDATA}/Microsoft/dotnet which we should use to build and publish the project
powershell.exe '.\integrations\dotnet\dotnet-install.ps1 -Channel 5.0 '

${LOCALAPPDATA}/Microsoft/dotnet/dotnet --version
${LOCALAPPDATA}/Microsoft/dotnet/dotnet --list-sdks

# /p required to get around https://github.com/dotnet/sdk/issues/12159
${LOCALAPPDATA}/Microsoft/dotnet/dotnet build mongo-csharp-driver /p:Platform="Any CPU" # platform needs a space when building
${LOCALAPPDATA}/Microsoft/dotnet/dotnet publish mongo-csharp-driver/tests/AstrolabeWorkloadExecutor \
    --no-build --no-restore \
    --framework "${FRAMEWORK}" \
    /p:Platform="AnyCpu" # platform does not need a space when publishing
