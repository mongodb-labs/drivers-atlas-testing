#!/usr/bin/env bash
set -o xtrace   # Write all commands first to stderr
set -o errexit  # Exit the script with error if any of the commands fail

# Environment variables used as input:
#   FRAMEWORK                       Set to specify .NET framework to test against. Values: "netcoreapp2.1"

dotnet --version
dotnet --list-sdks

# /p required to get around https://github.com/dotnet/sdk/issues/12159
dotnet build mongo-csharp-driver /p:Platform="Any CPU" # platform needs a space when building
dotnet publish mongo-csharp-driver/tests/AstrolabeWorkloadExecutor \
    --no-build --no-restore \
    --framework "${FRAMEWORK}" \
    /p:Platform="AnyCpu" # platform does not need a space when publishing
