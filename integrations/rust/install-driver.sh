#!/bin/bash

set -o errexit
set -o xtrace

rm -rf ~/.rustup
curl https://sh.rustup.rs -sSf | sh -s -- -y --no-modify-path

echo "export CARGO_NET_GIT_FETCH_WITH_CLI=true" >> ~/.cargo/env

source $HOME/.cargo/env

cargo build --manifest-path mongo-rust-driver/Cargo.toml --tests
