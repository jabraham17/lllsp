// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';
import { LanguageClient } from './LanguageClient';
import { initializePython, getInterpreterDetails } from './python';

let logger: vscode.LogOutputChannel;
let lc: LanguageClient;

// This method is called when your extension is activated
// Your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {

  logger = vscode.window.createOutputChannel("lllsp", { log: true });
  logger.info("llvm-language-server extension activated");

  const runServer = async () => {
    logger.trace(`Python extension loading`);
    initializePython(context.subscriptions, logger).then(() => {
      logger.trace(`Python extension loaded`);
      getInterpreterDetails().then((interpreterDetails) => {
        const p = interpreterDetails.path;
        if (p === undefined) {
          logger.error(
            'Python interpreter missing:\r\n' +
            '[Option 1] Select python interpreter using the ms-python.python.\n' +
            'Please use Python 3.8 or greater.',
          );
        } else {
          logger.info(`Using interpreter from Python extension: ${p.join(' ')}`);
          lc = new LanguageClient(p[0], logger);
          lc.start();
        }
      })
    });
  };


  context.subscriptions.push(vscode.commands.registerCommand('llvm-language-server.restart', async () => {
    runServer();
  }));
  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument(async () => {
      runServer();
    })
  );

}

// This method is called when your extension is deactivated
export function deactivate() {

  if (lc) {
    return lc.stop();
  }
  return new Promise(() => { });

}
