#!/usr/bin/env bash

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

# Make virtual env
if [ ! -d $FILE_DIR/.venv ]; then
  echo "Creating Python venv"
  python3 -m venv $FILE_DIR/.venv
fi
echo "Installing server"
$FILE_DIR/.venv/bin/pip install $FILE_DIR/server/

# Install editor support
$FILE_DIR/editors/vscode/install.sh
