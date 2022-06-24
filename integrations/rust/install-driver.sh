#!/bin/bash

set -o errexit
set -o xtrace

export WORKING_DIRECTORY=$(pwd)

export RUSTUP_HOME="$WORKING_DIRECTORY/.rustup"
export CARGO_HOME="$WORKING_DIRECTORY/.cargo"

curl https://sh.rustup.rs -sSf | sh -s -- -y --no-modify-path

echo "export CARGO_NET_GIT_FETCH_WITH_CLI=true" >> $WORKING_DIRECTORY/.cargo/env

source $WORKING_DIRECTORY/.cargo/env

cargo build --manifest-path mongo-rust-driver/Cargo.toml --tests --release
