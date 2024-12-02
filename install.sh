#!/usr/bin/env bash

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

# Make virtual env
if [ ! -d $FILE_DIR/.venv ]; then
  echo "Creating Python venv"
  python3 -m venv $FILE_DIR/.venv
fi
echo "Install Python dependencies"
# $FILE_DIR/.venv/bin/pip install -r $FILE_DIR/server/dev-requirements.txt
$FILE_DIR/.venv/bin/pip install server/

# Install editor support
$FILE_DIR/editors/vscode/install.sh
