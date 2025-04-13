// Copied and modified from https://github.com/chapel-lang/chapel-vscode/blob/main/src/ChapelLanguageClient.ts
/*
 * Copyright 2024-2024 Hewlett Packard Enterprise Development LP
 * Other additional copyright holders may be indicated within.
 *
 * The entirety of this work is licensed under the Apache License,
 * Version 2.0 (the "License"); you may not use this file except
 * in compliance with the License.
 *
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import * as fs from "fs";
import * as vscode from "vscode";
import * as vlc from "vscode-languageclient/node";
import * as path from "path";
import {EXTENSION_TOOL} from "./constants";

export enum LanguageClientState {
  DISABLED,
  STOPPED,
  STARTING,
  RUNNING,
  ERRORED,
}

class ErrorHandlingClient extends vlc.LanguageClient {
  infoHandler: (message: string, data?: any) => void;
  warningHandler: (message: string, data?: any) => void;
  errorHandler: (message: string, data?: any) => void;
  constructor(
    name: string,
    serverOptions: vlc.ServerOptions,
    clientOptions: vlc.LanguageClientOptions,
    infoHandler: (message: string, data?: any) => void,
    warningHandler: (message: string, data?: any) => void,
    errorHandler: (message: string, data?: any) => void
  ) {
    super(name, serverOptions, clientOptions);
    this.infoHandler = infoHandler;
    this.warningHandler = warningHandler;
    this.errorHandler = errorHandler;
  }

  override info(message: string, data?: any): void {
    this.infoHandler(message, data);
  }
  override warn(message: string, data?: any): void {
    this.warningHandler(message, data);
  }
  override error(message: string, data?: any): void {
    this.errorHandler(message, data);
  }
}

export class LanguageClient {
  python_path: string;
  name: string;
  state: LanguageClientState;
  client: ErrorHandlingClient | undefined;
  logger: vscode.LogOutputChannel;
  statusBarItem: vscode.StatusBarItem;

  constructor(
    python_path: string,
    logger: vscode.LogOutputChannel
  ) {
    this.python_path = python_path;
    this.name = "lllsp";
    this.state = LanguageClientState.STOPPED;
    this.client = undefined;
    this.logger = logger;
    this.statusBarItem = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      1000
    );
    // render the text using vscode codicons
    this.statusBarItem.text = `$(error) ${this.name}`;
    this.statusBarItem.tooltip = `${this.name} is stopped. Click to restart.`;
    this.statusBarItem.color = new vscode.ThemeColor(
      "statusBarItem.errorForeground"
    );
    this.statusBarItem.backgroundColor = new vscode.ThemeColor(
      "statusBarItem.errorBackground"
    );
    this.statusBarItem.command = `${this.name}.restart`;
    this.statusBarItem.hide();
  }

  async changePythonPath(python_path: string) {
    await this.stop();
    this.python_path = python_path;
    await this.start();
  }

  setErrorState() {
    this.state = LanguageClientState.ERRORED;
    this.statusBarItem.show();
  }

  clearError(): void {
    this.state = LanguageClientState.STOPPED;
  }


  start(): Promise<void> {
    if (this.state !== LanguageClientState.STOPPED) {
      return Promise.resolve();
    }
    this.state = LanguageClientState.STARTING;
    this.statusBarItem.hide();


    let command = this.python_path;
    let args = [EXTENSION_TOOL];

    this.logger.info(`${this.name} command: '${command}'`);
    this.logger.info(`${this.name} args: '${args}'`);

    const serverOptions: vlc.ServerOptions = {
      command: command,
      args: args,
    };
    this.logger.debug(
      `${this.name} server options ${JSON.stringify(
        serverOptions,
        undefined,
        2
      )}`
    );

    const errorLogger = (message: string) => {
      this.logger.error(`${this.name}: ${message}`);
    };
    const infoLogger = (message: string, data?: any) => {
      if (data) {
        this.logger.info(
          `${this.name}: ${message} - ${JSON.stringify(data, undefined, 2)}`
        );
      } else {
        this.logger.info(`${this.name}: ${message}`);
      }
    };
    const warningLogger = (message: string, data?: any) => {
      if (data) {
        this.logger.warn(
          `${this.name}: ${message} - ${JSON.stringify(data, undefined, 2)}`
        );
      } else {
        this.logger.warn(`${this.name}: ${message}`);
      }
    };
    const errorHandler = (message: string, data?: any) => {
      if (data) {
        errorLogger(`${message} - ${JSON.stringify(data, undefined, 2)}`);
      } else {
        errorLogger(message);
      }

      this.stop().finally(() => {
        this.setErrorState();

        vscode.window
          .showErrorMessage(
            `${this.name} encountered an unrecoverable error`,
            "Restart",
            "Show Log",
            "Ok"
          )
          .then((value) => {
            if (value === "Restart") {
              this.restart();
            } else if (value === "Show Log") {
              this.logger.show();
            }
          });
      });
    };

    const clientOptions: vlc.LanguageClientOptions = {
      documentSelector: [
        {
          scheme: "file",
          language: "llvm",
        },
      ],
      outputChannel: this.logger,
      connectionOptions: {
        maxRestartCount: 0,
      },
      initializationFailedHandler: () => {
        // always return false to trigger other error handlers
        return false;
      },
      errorHandler: {
        error: (error) => {
          errorHandler(error.message, true);
          return { action: vlc.ErrorAction.Shutdown, handled: true };
        },
        closed: () => {
          errorHandler("Server closed", true);
          return { action: vlc.CloseAction.DoNotRestart, handled: true };
        },
      },
    };
    this.logger.debug(
      `${this.name} server options ${JSON.stringify(
        serverOptions,
        undefined,
        2
      )}`
    );

    this.client = new ErrorHandlingClient(
      this.name,
      serverOptions,
      clientOptions,
      infoLogger,
      warningLogger,
      errorHandler
    );

    this.client.onDidChangeState((event) => {
      if (event.newState === vlc.State.Stopped) {
        this.state = LanguageClientState.STOPPED;
      } else if (event.newState === vlc.State.Running) {
        this.state = LanguageClientState.RUNNING;
      }
    });

    return this.client.start();
  }

  stop(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.client && this.state === LanguageClientState.RUNNING) {
        this.client.errorHandler = () => {};
        this.client.stop().catch(reject);
        this.client.dispose();
        this.client = undefined;
      }
      resolve();
    });
  }

  restart(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.stop()
        .then(() => {
          this.clearError();
          this.start().then(resolve).catch(reject);
        })
        .catch(reject);
    });
  }
}
