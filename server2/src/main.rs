use tower_lsp::{LspService, Server};

use crate::lsp::Backend;

mod ir;
mod lsp;
mod parser;
mod reader;

#[tokio::main]
async fn main() {
  let stdin = tokio::io::stdin();
  let stdout = tokio::io::stdout();

  let (service, socket) = LspService::new(|client| Backend::new(client));
  Server::new(stdin, stdout, socket).serve(service).await;
}
