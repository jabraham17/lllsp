#!/usr/bin/env bash

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

set -x

rm -rf $FILE_DIR/.venv
rm -rf $FILE_DIR/server/build
rm -rf $FILE_DIR/server/dist
rm -rf $FILE_DIR/server/lllsp.egg-info
