#!/usr/bin/env bash

echo "Running C Driver install-driver.sh..."

# Defined by .evergreen/config.yml.
echo "CC: ${CC:?}"
echo "CXX: ${CXX:?}"

# Ensure required binaries are present.
command -V "${CC}" >/dev/null || exit
command -V "${CXX}" >/dev/null || exit

# Cloned by .evergreen/config.yml.
pushd mongo-c-driver || exit

declare c_install_dir
c_install_dir="$(pwd)/install-dir" || exit

# Obtain latest CMake binary via C Driver Evergreen testing scripts.
# shellcheck source=/dev/null
. "$(pwd)/.evergreen/scripts/find-cmake-latest.sh" || exit
declare cmake_binary
cmake_binary="$(find_cmake_latest)" || exit
command -V "${cmake_binary}" >/dev/null || exit

# /opt/mongodbtoolchain/v4/bin/ninja is buggy:
#     ninja: error: manifest 'build.ninja' still dirty after 100 tries
# Use GNU Make and specify build parallelism manually instead.
declare jobs
jobs="$(nproc)" || exit

declare -a cmake_config_vars=(
  "-DCMAKE_BUILD_TYPE=RelWithDebInfo"
  "-DCMAKE_INSTALL_PREFIX=${c_install_dir}"
  "-DENABLE_AUTOMATIC_INIT_AND_CLEANUP=OFF"
  "-DENABLE_EXTRA_ALIGNMENT=OFF" # Interferes with ASAN.
)

# Unable to compile with ASAN/UBSAN using GCC on ubuntu1804-drivers-atlas-testing.
if [[ "${CC}" =~ clang ]]; then
  cmake_config_vars+=("-DMONGO_SANITIZE=address,undefined")
  cmake_config_vars+=("-DENABLE_SASL=OFF") # Interferes with LSAN.
fi

"${cmake_binary}" "${cmake_config_vars[@]}" || exit
"${cmake_binary}" --build . --target test-atlas-executor -- -j "${jobs}" || exit

popd || exit # mongo-c-driver

echo "Running C Driver install-driver.sh... done!"
