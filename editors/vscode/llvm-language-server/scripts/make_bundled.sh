#!/usr/bin/env bash
set -e

FILE_DIR=$(cd $(dirname ${BASH_SOURCE[0]}) ; pwd)

BUNDLED=$FILE_DIR/../bundled

rm -rf $BUNDLED
mkdir -p $BUNDLED
python3 -m pip install -t $BUNDLED/libs --no-cache-dir --implementation py --no-deps --upgrade -r $FILE_DIR/../requirements.txt $FILE_DIR/../../../../server/

