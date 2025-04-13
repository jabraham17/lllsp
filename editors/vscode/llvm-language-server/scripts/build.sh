#!/usr/bin/env bash
set -e

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

VSCODE_DIR=$(cd $FILE_DIR/.. ; pwd )

echo "npm install"
(cd $VSCODE_DIR && npm install)
