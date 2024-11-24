#!/usr/bin/env bash

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

# Make virtual env
python3 -m venv $FILE_DIR/.venv
$FILE_DIR/.venv/bin/pip install -r $FILE_DIR/server/dev-requirements.txt -r $FILE_DIR/server/runtime-requirements.txt

# Install editor support
$FILE_DIR/editors/vscode/install.sh
