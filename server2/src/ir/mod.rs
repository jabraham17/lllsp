use std::cmp::Ordering;

#[derive(Default, Clone, Copy, PartialEq, Eq)]
pub struct Position {
  pub column: usize,
  pub line: usize,
}

impl Position {
  pub fn new(column: usize, line: usize) -> Self {
    Self { column, line }
  }
}

impl PartialOrd for Position {
  fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
    Some(self.cmp(other))
  }
}

impl Ord for Position {
  fn cmp(&self, other: &Self) -> Ordering {
    match self.line.cmp(&other.line) {
      Ordering::Equal => self.column.cmp(&other.column),
      o => o,
    }
  }
}

#[derive(Default, Clone, PartialEq, Eq)]
pub struct Range {
  pub start: Position,
  pub end: Position,
}

impl Range {
  pub fn new(start: Position, end: Position) -> Self {
    Self { start, end }
  }

  pub fn contains_range(&self, other: &Range) -> bool {
    other.start >= self.start && other.end <= self.end
  }

  pub fn contains_position(&self, pos: &Position) -> bool {
    pos >= &self.start && pos <= &self.end
  }
}

#[derive(Default, Clone, PartialEq, Eq)]
pub struct Location {
  pub filename: String,
  pub rng: Range,
}

impl Location {
  pub fn new(filename: impl Into<String>, rng: Range) -> Self {
    Self {
      filename: filename.into(),
      rng,
    }
  }
}
impl std::fmt::Debug for Position {
  fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
    write!(f, "{:}:{:}", self.line + 1, self.column)
  }
}
impl std::fmt::Debug for Range {
  fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
    write!(f, "{:?}-{:?}", self.start, self.end)
  }
}
impl std::fmt::Debug for Location {
  fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
    write!(f, "{:}:{:?}", self.filename, self.rng)
  }
}

// --- IR types ---

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NameKind {
  Bare(String),
  Value(String),
  Symbol(String),
  Metadata(String),
  Attribute(String),
  Label(String),
}
impl NameKind {
  pub fn str(&self) -> &String {
    match self {
      NameKind::Bare(s) => s,
      NameKind::Value(s) => s,
      NameKind::Symbol(s) => s,
      NameKind::Metadata(s) => s,
      NameKind::Attribute(s) => s,
      NameKind::Label(s) => s,
    }
  }
}

#[derive(Clone, PartialEq, Eq)]
pub struct Name {
  pub location: Location,
  pub kind: NameKind,
}

impl Name {
  pub fn basename(&self) -> String {
    match &self.kind {
      NameKind::Bare(s) => s.clone(),
      NameKind::Value(s) => s.strip_prefix("%").unwrap_or(s).to_string(),
      NameKind::Symbol(s) => s.strip_prefix("@").unwrap_or(s).to_string(),
      NameKind::Metadata(s) => s.strip_prefix("!").unwrap_or(s).to_string(),
      NameKind::Attribute(s) => s.strip_prefix("#").unwrap_or(s).to_string(),
      NameKind::Label(s) => s.strip_suffix(":").unwrap_or(s).to_string(),
    }
  }
}

impl std::fmt::Debug for Name {
  fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
    write!(f, "'{:}' at {:?}", self.kind.str(), self.location)
  }
}

#[derive(Debug, Clone)]
pub struct SourceFilename {
  pub location: Location,
  pub filename: String,
}

#[derive(Debug, Clone)]
pub struct TargetString {
  pub location: Location,
  pub kind: String,
  pub value: String,
}

#[derive(Debug, Clone)]
pub struct TypeDefinition {
  pub location: Location,
  pub name: Name,
}

#[derive(Debug, Clone)]
pub struct Formal {
  pub location: Location,
  pub name: Name,
}

#[derive(Debug, Clone)]
pub struct Statement {
  pub location: Location,
  pub value: Name,
}

#[derive(Debug, Clone)]
pub struct Label {
  pub location: Location,
  pub name: String,
}

#[derive(Debug, Clone)]
pub struct Define {
  pub location: Location,
  pub name: Name,
  pub formals: Vec<Formal>,
  pub statements: Vec<StatementOrLabel>,
}
impl Define {
  pub fn resolve(&self, i: &Name) -> Option<IRNode> {
    for s in &self.statements {
      match s {
        StatementOrLabel::Stmt(stmt) => {
          if stmt.value.basename() == i.basename() {
            return Some(IRNode::Statement(stmt.clone()));
          }
        }
        StatementOrLabel::Label(lbl) => {
          if lbl.name == i.basename() {
            return Some(IRNode::Label(lbl.clone()));
          }
        }
      }
    }
    None
  }
}

#[derive(Debug, Clone)]
pub struct Declare {
  pub location: Location,
  pub name: Name,
  pub formals: Vec<Formal>,
}

#[derive(Debug, Clone)]
pub enum Function {
  Define(Define),
  Declare(Declare),
}

impl Function {
  pub fn resolve(&self, i: &Name) -> Option<IRNode> {
    // search formals first
    let formals = match self {
      Function::Define(d) => &d.formals,
      Function::Declare(de) => &de.formals,
    };
    for f in formals {
      if f.name.basename() == i.basename() {
        return Some(IRNode::Formal(f.clone()));
      }
    }
    if let Function::Define(d) = self {
      return d.resolve(i);
    }
    None
  }
}

#[derive(Debug, Clone)]
pub enum StatementOrLabel {
  Stmt(Statement),
  Label(Label),
}

#[derive(Debug, Clone)]
pub struct Constant {
  pub location: Location,
  pub name: Name,
}

#[derive(Debug, Clone)]
pub struct Metadata {
  pub location: Location,
  pub name: Name,
}

#[derive(Debug, Clone)]
pub struct Attribute {
  pub location: Location,
  pub name: Name,
}

#[derive(Debug, Clone)]
pub enum IRNode {
  SourceFilename(SourceFilename),
  TargetString(TargetString),
  TypeDefinition(TypeDefinition),
  Constant(Constant),
  Function(Function),
  Metadata(Metadata),
  Attribute(Attribute),
  Formal(Formal),
  Statement(Statement),
  Label(Label),
}

impl IRNode {
  pub fn location(&self) -> &Location {
    match self {
      IRNode::SourceFilename(sf) => &sf.location,
      IRNode::TargetString(ts) => &ts.location,
      IRNode::TypeDefinition(td) => &td.location,
      IRNode::Constant(c) => &c.location,
      IRNode::Function(f) => match f {
        Function::Define(d) => &d.location,
        Function::Declare(de) => &de.location,
      },
      IRNode::Metadata(m) => &m.location,
      IRNode::Attribute(a) => &a.location,
      IRNode::Formal(f) => &f.location,
      IRNode::Statement(s) => &s.location,
      IRNode::Label(l) => &l.location,
    }
  }
}

#[derive(Debug, Default, Clone)]
pub struct Module {
  pub location: Location,
  pub source_filename: Option<SourceFilename>,
  pub target_info: Vec<TargetString>,
  pub types: Vec<TypeDefinition>,
  pub constants: Vec<Constant>,
  pub functions: Vec<Function>,
  pub metadata: Vec<Metadata>,
  pub attributes: Vec<Attribute>,
}

impl Module {
  pub fn new(location: Location) -> Self {
    Self {
      location,
      ..Default::default()
    }
  }

  pub fn add(&mut self, node: IRNode) {
    match node {
      IRNode::SourceFilename(sf) => self.source_filename = Some(sf),
      IRNode::TargetString(ts) => self.target_info.push(ts),
      IRNode::TypeDefinition(td) => self.types.push(td),
      IRNode::Constant(c) => self.constants.push(c),
      IRNode::Function(f) => self.functions.push(f),
      IRNode::Metadata(m) => self.metadata.push(m),
      IRNode::Attribute(a) => self.attributes.push(a),
      IRNode::Formal(_) => {}
      IRNode::Statement(_) => {}
      IRNode::Label(_) => {}
    }
  }

  pub fn resolve(&self, i: &Name) -> Option<IRNode> {
    // If ValueName: search functions whose ranges contain the name's location
    if let NameKind::Value(_) = &i.kind {
      for f in &self.functions {
        let func_loc = match f {
          Function::Define(d) => &d.location,
          Function::Declare(de) => &de.location,
        };
        if func_loc.rng.contains_position(&i.location.rng.start) {
          if let Some(res) = f.resolve(i) {
            return Some(res);
          }
        }
      }

      // typedefs
      for t in &self.types {
        if let NameKind::Value(name_str) = &i.kind {
          if t.name.basename() == *name_str {
            return Some(IRNode::TypeDefinition(t.clone()));
          }
        }
      }
      return None;
    }

    // SymbolName
    if let NameKind::Symbol(_) = &i.kind {
      for f in &self.functions {
        match f {
          Function::Define(d) => {
            if d.name.basename() == i.basename() {
              return Some(IRNode::Function(Function::Define(d.clone())));
            }
          }
          Function::Declare(de) => {
            if de.name.basename() == i.basename() {
              return Some(IRNode::Function(Function::Declare(de.clone())));
            }
          }
        }
      }
      for c in &self.constants {
        if c.name.basename() == i.basename() {
          return Some(IRNode::Constant(c.clone()));
        }
      }
    }

    // MetadataName
    if let NameKind::Metadata(_) = &i.kind {
      for m in &self.metadata {
        if m.name.basename() == i.basename() {
          return Some(IRNode::Metadata(m.clone()));
        }
      }
    }

    // AttributeName
    if let NameKind::Attribute(_) = &i.kind {
      for a in &self.attributes {
        if a.name.basename() == i.basename() {
          return Some(IRNode::Attribute(a.clone()));
        }
      }
    }

    None
  }
}

#[cfg(test)]
#[path = "./test.rs"]
mod test;
