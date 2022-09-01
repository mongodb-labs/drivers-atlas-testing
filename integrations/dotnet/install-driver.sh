#!/usr/bin/env bash
set -o xtrace   # Write all commands first to stderr
set -o errexit  # Exit the script with error if any of the commands fail

# Environment variables used as input:
#   FRAMEWORK                       Set to specify .NET framework to test against. Values: "netcoreapp2.1"

export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_CLI_TELEMETRY_OPTOUT=1

if [[ "$OS" =~ Windows|windows ]]; then
    export DOTNET_CLI_HOME="Z:/"
    export TMP="Z:/"
    export TEMP="Z:/"
    export NUGET_PACKAGES="Z:/"
    export NUGET_HTTP_CACHE_PATH="Z:/"
    export APPDATA="Z:/"

    # Download the dotnet installation script, retrying up to 5 times on any errors.
    curl -sSL \
        --max-time 20 \
        --retry 5 \
        --retry-delay 0 \
        --retry-max-time 60 \
        --retry-all-errors \
        -o integrations/dotnet/dotnet-install.ps1 \
        https://dot.net/v1/dotnet-install.ps1

    # Install the v5.0 SDK to build the driver and the v2.1 SDK to run the published workload
    # executor binaries.
    powershell.exe '.\integrations\dotnet\dotnet-install.ps1 -Channel 5.0 -InstallDir .dotnet -NoPath'
    powershell.exe '.\integrations\dotnet\dotnet-install.ps1 -Channel 2.1 -InstallDir .dotnet -NoPath'
else
    # Download the dotnet installation script, retrying up to 5 times on any errors.
    curl -sSL \
        --max-time 20 \
        --retry 5 \
        --retry-delay 0 \
        --retry-max-time 60 \
        -o integrations/dotnet/dotnet-install.sh \
        https://dot.net/v1/dotnet-install.sh

    # Install the v5.0 SDK to build the driver and the v2.1 SDK to run the published workload
    # executor binaries.
    bash ./integrations/dotnet/dotnet-install.sh -Channel 5.0 --install-dir .dotnet --no-path
    bash ./integrations/dotnet/dotnet-install.sh -Channel 2.1 --install-dir .dotnet --no-path
fi

# /p required to get around https://github.com/dotnet/sdk/issues/12159
./.dotnet/dotnet build mongo-csharp-driver /p:Platform="Any CPU" # platform needs a space when building
./.dotnet/dotnet publish mongo-csharp-driver/tests/AstrolabeWorkloadExecutor \
    --no-build --no-restore \
    --framework "${FRAMEWORK}" \
    /p:Platform="AnyCpu" # platform does not need a space when publishing
