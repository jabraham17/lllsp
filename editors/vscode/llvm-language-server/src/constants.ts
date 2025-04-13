// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';

export const EXTENSION_ROOT_DIR = path.dirname(__dirname);
export const BUNDLED_PYTHON_SCRIPTS_DIR = path.join(EXTENSION_ROOT_DIR, 'bundled');
export const EXTENSION_TOOL = path.join(EXTENSION_ROOT_DIR, "tool", "lllsp.py");
