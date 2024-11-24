#!/usr/bin/env bash

# get the current directory
FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)
VSCODE_DIR=$FILE_DIR/../../.vscode

# if the code executable, exists, use it to install the required extensions
if ! command -v code 2>&1 >/dev/null; then
  echo "'code' is not installed"
  exit 1
fi

echo "Installing 'sunshaoce.llvmir' and 'torokati44.glspc'"
code --install-extension sunshaoce.llvmir
code --install-extension torokati44.glspc

echo "Setting up 'glspc' for LLVM"

LLLSP_PATH=$(cd $FILE_DIR/../../server ; pwd)/lllsp
if [ ! -d $VSCODE_DIR ]; then
  echo "Creating directory $VSCODE_DIR"
  mkdir -p $VSCODE_DIR
  VSCODE_DIR=$(cd $VSCODE_DIR ; pwd)
fi
VSCODE_SETTINGS=$VSCODE_DIR/settings.json
if [ ! -f $VSCODE_SETTINGS ]; then
  # if the settings don't already exist, just create them
  echo "Creating new settings"
  touch $VSCODE_SETTINGS
  echo "{" >> $VSCODE_SETTINGS
  echo "  \"glspc.serverPath\": \"$LLLSP_PATH\"," >> $VSCODE_SETTINGS
  echo "  \"glspc.languageId\": \"llvm\"" >> $VSCODE_SETTINGS
  echo "}" >> $VSCODE_SETTINGS
else

  if ! command -v jq 2>&1 >/dev/null; then
    echo "'jq' is not installed, settings will not be updated automatically"
    exit 0
  fi

  CUR_SERVER_PATH=$(jq -r '."glspc.serverPath"' $VSCODE_SETTINGS)
  if [[ "$CUR_SERVER_PATH" != "$LLLSP_PATH" ]]; then
    echo "Updating 'glspc.serverPath' to '$LLLSP_PATH'"
    jq ".\"glspc.serverPath\" = \"$LLLSP_PATH\"" $VSCODE_SETTINGS > $VSCODE_SETTINGS.tmp
    mv $VSCODE_SETTINGS.tmp $VSCODE_SETTINGS
  fi

  CUR_LANG=$(jq -r '."glspc.languageId"' $VSCODE_SETTINGS)
  if [[ "$CUR_LANG" != "llvm" ]]; then
    echo "Updating 'glspc.languageId' to 'llvm'"
    jq '."glspc.languageId" = "llvm"' $VSCODE_SETTINGS > $VSCODE_SETTINGS.tmp
    mv $VSCODE_SETTINGS.tmp $VSCODE_SETTINGS
  fi
fi
