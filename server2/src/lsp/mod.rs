use std::path::PathBuf;

use rustc_hash::FxHashMap;
use tokio::sync::Mutex;
use tower_lsp::jsonrpc::Result;
use tower_lsp::lsp_types::{self as lspT, TextDocumentSyncSaveOptions};
use tower_lsp::lsp_types::{
  Diagnostic, DiagnosticSeverity, DidOpenTextDocumentParams,
  DidSaveTextDocumentParams, GotoDefinitionParams, GotoDefinitionResponse,
  InitializeParams, InitializeResult, InitializedParams, MessageType, OneOf,
  ServerCapabilities, TextDocumentSyncCapability, TextDocumentSyncOptions, Url,
};
use tower_lsp::{Client, LanguageServer, LspService, Server};

use crate::ir::{self, Module, Name};
use crate::lsp;
use crate::lsp::position_list::PositionList;
use crate::parser::{IRParser, NameParser};
use crate::reader::FileReader;

mod position_list;

fn pos_to_lsp(pos: &ir::Position) -> lspT::Position {
  lspT::Position {
    line: pos.line as u32,
    character: pos.column as u32,
  }
}
fn rng_to_lsp(rng: &ir::Range) -> lspT::Range {
  lspT::Range {
    start: pos_to_lsp(&rng.start),
    end: pos_to_lsp(&rng.end),
  }
}
fn loc_to_lsp(loc: &ir::Location) -> lspT::Location {
  lspT::Location {
    uri: lspT::Url::from_file_path(&loc.filename).unwrap(),
    range: rng_to_lsp(&loc.rng),
  }
}

#[derive(Debug, Clone)]
struct LSPIRName {
  pub name: Name,
}
impl LSPIRName {
  pub fn new(name: Name) -> Self {
    Self { name }
  }
  pub fn rng(&self) -> lspT::Range {
    rng_to_lsp(&self.name.location.rng)
  }
}

#[derive(Debug)]
struct FileInfo {
  uri: Url,
  module: Module,
  name_segments: PositionList<LSPIRName>,
}
impl FileInfo {
  fn new(uri: Url, module: Module) -> Self {
    let name_segments = PositionList::new(LSPIRName::rng);
    Self {
      uri,
      module,
      name_segments,
    }
  }
  fn build_name_segments(&mut self, names: &Vec<ir::Name>) {
    self.name_segments.clear();
    for name in names.iter() {
      let lsp_name = LSPIRName::new(name.clone());
      self.name_segments.append(lsp_name);
    }
    self.name_segments.sort();
  }

  fn find_name_segment(&self, pos: &lspT::Position) -> Option<&LSPIRName> {
    match self.name_segments.find(pos) {
      Some(idx) => Some(&self.name_segments.elts[idx]),
      None => None,
    }
  }
  fn resolve(&self, name: &LSPIRName) -> Option<ir::IRNode> {
    self.module.resolve(&name.name)
  }
}

#[derive(Debug)]
struct State {
  parser: IRParser,
  name_parser: NameParser,
  docs: FxHashMap<Url, FileInfo>,
}
impl State {
  fn new() -> Self {
    Self {
      parser: IRParser::new(),
      name_parser: NameParser::new(),
      docs: FxHashMap::default(),
    }
  }
  fn build_fi(&self, uri: &Url) -> Result<FileInfo> {
    let path = uri.to_file_path().map_err(|_| {
      tower_lsp::jsonrpc::Error::invalid_params("Invalid file URI")
    })?;
    let mut reader = FileReader::open(&path)
      .map_err(|_| tower_lsp::jsonrpc::Error::internal_error())?;
    let module = self.parser.parse(&mut reader);
    reader
      .reset()
      .map_err(|_| tower_lsp::jsonrpc::Error::internal_error())?;
    let names = self.name_parser.parse(&mut reader);
    let mut file_info = FileInfo::new(uri.clone(), module);
    file_info.build_name_segments(&names);
    Ok(file_info)
  }
  fn get_file(&mut self, uri: &Url) -> Result<&FileInfo> {
    if self.docs.contains_key(uri) {
      Ok(self.docs.get(uri).unwrap())
    } else {
      let fi = self.build_fi(uri)?;
      self.docs.insert(uri.clone(), fi);
      Ok(self.docs.get(uri).unwrap())
    }
  }
  fn reload_file(&mut self, uri: &Url) -> Result<&FileInfo> {
    let fi = self.build_fi(uri)?;
    self.docs.insert(uri.clone(), fi);
    Ok(self.docs.get(uri).unwrap())
  }
}

#[derive(Debug)]
pub struct Backend {
  client: Client,
  state: Mutex<State>,
}

impl Backend {
  pub fn new(client: Client) -> Self {
    Self {
      client,
      state: Mutex::new(State::new()),
    }
  }
}

fn dummy_diag(uri: &Url) -> Diagnostic {
  let diag = Diagnostic {
    range: lspT::Range::new(
      lspT::Position::new(0, 0),
      lspT::Position::new(0, 1),
    ),
    severity: Some(DiagnosticSeverity::INFORMATION),
    code: None,
    code_description: None,
    source: Some("minimal_lsp".into()),
    message: "dummy diagnostic".into(),
    related_information: None,
    tags: None,
    data: None,
  };
  diag
}

fn server_capabilities() -> ServerCapabilities {
  ServerCapabilities {
    text_document_sync: Some(TextDocumentSyncCapability::Options(
      TextDocumentSyncOptions {
        open_close: Some(true),
        save: Some(TextDocumentSyncSaveOptions::Supported(true)),
        ..Default::default()
      },
    )),
    definition_provider: Some(OneOf::Left(true)),
    ..Default::default()
  }
}

#[tower_lsp::async_trait]
impl LanguageServer for Backend {
  async fn initialize(&self, _: InitializeParams) -> Result<InitializeResult> {
    Ok(InitializeResult {
      capabilities: server_capabilities(),
      server_info: None,
    })
  }

  async fn initialized(&self, _: InitializedParams) {
    self
      .client
      .log_message(MessageType::INFO, "server initialized!")
      .await;
  }

  async fn did_open(&self, params: DidOpenTextDocumentParams) {
    let uri = params.text_document.uri;
    self
      .client
      .log_message(MessageType::INFO, format!("Opened file: {}", uri))
      .await;
    let mut state = self.state.lock().await;
    if let Err(e) = state.reload_file(&uri) {
      self
        .client
        .log_message(
          MessageType::ERROR,
          format!("Error reloading file {}: {}", uri, e),
        )
        .await;
      return;
    }
  }

  async fn did_save(&self, params: DidSaveTextDocumentParams) {
    let uri = params.text_document.uri;
    self
      .client
      .log_message(MessageType::INFO, format!("Saved file: {}", uri))
      .await;
    let mut state = self.state.lock().await;
    if let Err(e) = state.reload_file(&uri) {
      self
        .client
        .log_message(
          MessageType::ERROR,
          format!("Error reloading file {}: {}", uri, e),
        )
        .await;
      return;
    }

    self
      .client
      .publish_diagnostics(uri.clone(), vec![dummy_diag(&uri)], None)
      .await;
  }

  async fn goto_definition(
    &self,
    params: GotoDefinitionParams,
  ) -> Result<Option<GotoDefinitionResponse>> {
    let uri = params.text_document_position_params.text_document.uri;
    let pos = params.text_document_position_params.position;
    self
      .client
      .log_message(
        MessageType::INFO,
        format!(
          "Goto definition at {} (line {}, character {})",
          uri, pos.line, pos.character
        ),
      )
      .await;

    let mut state = self.state.lock().await;
    let fi = state.get_file(&uri);
    match fi {
      Ok(fi) => {
        let loc = match fi.find_name_segment(&pos) {
          Some(name) => match fi.resolve(name) {
            Some(node) => Some(loc_to_lsp(node.location())),
            None => None,
          },
          None => None,
        };
        Ok(loc.map(|l| GotoDefinitionResponse::Scalar(l)))
      }
      Err(e) => {
        self
          .client
          .log_message(
            MessageType::ERROR,
            format!("Error getting file {}: {}", uri, e),
          )
          .await;
        Ok(None)
      }
    }
  }

  async fn shutdown(&self) -> Result<()> {
    Ok(())
  }
}

#[cfg(test)]
#[path = "./test_resolve.rs"]
mod test_resolve;
