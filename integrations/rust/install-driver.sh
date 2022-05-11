#!/bin/bash

rm -rf ~/.rustup
curl https://sh.rustup.rs -sSf | sh -s -- -y --no-modify-path $DEFAULT_HOST_OPTIONS

echo "export CARGO_NET_GIT_FETCH_WITH_CLI=true" >> ~/.cargo/env

source ~/.cargo/env

cd mongo-rust-driver
cargo build --tests
