#!/usr/bin/env bash
set -e

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

BUNDLED=$FILE_DIR/../bundled

rm -rf $BUNDLED
mkdir -p $BUNDLED

SERVER2=$FILE_DIR/../../../../server2/

(cd $SERVER2 && cargo build --release)
cp $SERVER2/target/release/server2 $BUNDLED/llvm-language-server
