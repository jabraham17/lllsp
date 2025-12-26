use pcre2::bytes::Regex;

use crate::ir;
use crate::reader::{FileReader, Location as RLocation, Position as RPosition};
use crate::reader::{peek_char, peek_str, read_char};

fn rdr_pos_to_ir(p: &RPosition) -> ir::Position {
  ir::Position::new(p.col, p.line)
}

fn rdr_range_to_ir(start: &RPosition, end: &RPosition) -> ir::Range {
  ir::Range::new(rdr_pos_to_ir(start), rdr_pos_to_ir(end))
}

fn rdr_loc_to_ir(loc: &RLocation) -> ir::Location {
  ir::Location::new(
    loc.filename.to_string_lossy(),
    rdr_range_to_ir(&loc.range.start, &loc.range.end),
  )
}

#[derive(Debug)]
pub struct IRParser {
  value_name_re: Regex,
  label_re: Regex,
  formal_re: Regex,
}

impl IRParser {
  pub fn new() -> Self {
    Self {
      value_name_re: Regex::new(r"^ *(%[a-zA-Z0-9_.]+)").unwrap(),
      label_re: Regex::new(r"^ *([a-zA-Z0-9_.]+:)").unwrap(),
      formal_re: Regex::new(r"\(?\s*([^,]*(%[a-zA-Z0-9_.]+)[^,()]*)(?=,|\))?")
        .unwrap(),
    }
  }

  pub fn parse(&self, reader: &mut FileReader) -> ir::Module {
    let start = rdr_pos_to_ir(&reader.position());
    let dummy_loc = ir::Location::new("", ir::Range::new(start, start));
    let mut module = ir::Module::new(dummy_loc.clone());

    loop {
      match reader.eof() {
        Ok(true) => break,
        Ok(false) => {}
        Err(_) => break,
      }
      if let Some(node) = self.parse_one(reader) {
        module.add(node);
      }
    }

    let end = rdr_pos_to_ir(&reader.position());
    module.location = ir::Location::new(
      reader.filename.to_string_lossy(),
      ir::Range::new(start, end),
    );
    module
  }

  pub fn parse_one(&self, reader: &mut FileReader) -> Option<ir::IRNode> {
    let _ = reader.skip(" \t");
    let c = peek_char(reader).unwrap_or('\0');
    if c == ';' {
      self.parse_comment(reader);
      return None;
    } else if c == 's' || c == 't' {
      let _ = reader.through("\n");
      return None;
    } else if c == 'd' {
      let c3 = peek_str(reader, 3).unwrap_or_default();
      if c3 == "def" {
        return self._parse_define(reader);
      } else if c3 == "dec" {
        return self._parse_declare(reader);
      } else {
        let _ = reader.through("\n");
        return None;
      }
    } else if c == '%' {
      return self._parse_percent_named(reader).map(|n| n);
    } else if c == '@' {
      return self._parse_constant(reader).map(|c| c);
    } else if c == 'a' {
      return self._parse_attribute(reader).map(|a| a);
    } else if c == '!' {
      return self._parse_metadata(reader).map(|m| m);
    } else {
      let _ = reader.through("\n");
      return None;
    }
  }

  fn parse_comment(&self, reader: &mut FileReader) {
    let c = read_char(reader).unwrap_or('\0');
    if c != ';' {
      return;
    }
    let _ = reader.through("\n");
  }

  fn _read_block(
    &self,
    reader: &mut FileReader,
    start: &str,
    end: &str,
  ) -> String {
    let mut text = String::new();
    text.push_str(&reader.through(start).unwrap_or_default());
    let mut pairs = 1i32;
    while pairs != 0 {
      text.push_str(
        &reader
          .until(&(start.to_string() + end).as_str())
          .unwrap_or_default(),
      );
      let n = read_char(reader).unwrap_or('\0');
      text.push(n);
      if n.to_string() == start {
        pairs += 1;
      } else {
        pairs -= 1;
      }
    }
    text
  }

  fn _read_curly_block(&self, reader: &mut FileReader) -> String {
    self._read_block(reader, "{", "}")
  }

  fn _parse_statements(
    &self,
    reader: &mut FileReader,
  ) -> Vec<ir::StatementOrLabel> {
    let start = rdr_pos_to_ir(&reader.position());
    let text = self._read_curly_block(reader);
    let lines: Vec<&str> = text.lines().collect();
    let mut stmts = Vec::new();
    for (lineno, l) in lines.iter().enumerate() {

      if let Some(m) = self.value_name_re.captures(l.as_bytes()).ok().flatten() {
        let m = m.get(1).unwrap();
        let start_col = if lineno == 0 {
          start.column + m.start()
        } else {
          m.start()
        };
        let end_col = if lineno == 0 {
          start.column + m.end()
        } else {
          m.end()
        };
        let name_start = ir::Position::new(start_col, start.line + lineno);
        let name_end = ir::Position::new(end_col, start.line + lineno);
        let stmt_end =
          ir::Position::new(start.column + l.len(), start.line + lineno);
        let loc = ir::Location::new(
          reader.filename.to_string_lossy(),
          ir::Range::new(name_start, name_end),
        );
        let name = ir::Name {
          location: loc.clone(),
          kind: ir::NameKind::Value(
            String::from_utf8_lossy(m.as_bytes()).to_string(),
          ),
        };
        let stmt_loc = ir::Location::new(
          reader.filename.to_string_lossy(),
          ir::Range::new(name_start, stmt_end),
        );
        let s = ir::Statement {
          location: stmt_loc,
          value: name,
        };
        stmts.push(ir::StatementOrLabel::Stmt(s));
      } else if let Some(m) = self.label_re.captures(l.as_bytes()).ok().flatten() {
        let m = m.get(1).unwrap();
        let start_col = if lineno == 0 {
          start.column + m.start()
        } else {
          m.start()
        };
        let end_col = if lineno == 0 {
          start.column + m.end()
        } else {
          m.end()
        };
        let name_start = ir::Position::new(start_col, start.line + lineno);
        let name_end = ir::Position::new(end_col, start.line + lineno);
        let loc = ir::Location::new(
          reader.filename.to_string_lossy(),
          ir::Range::new(name_start, name_end),
        );
        let label = ir::Label {
          location: loc,
          name: String::from_utf8_lossy(m.as_bytes()).to_string(),
        };
        stmts.push(ir::StatementOrLabel::Label(label));
      }
    }
    stmts
  }

  fn _parse_formals(&self, reader: &mut FileReader) -> Vec<ir::Formal> {
    let start_r = reader.position();
    let text = self._read_block(reader, "(", ")");
    if text
      .trim()
      .trim_start_matches('(')
      .trim_end_matches(')')
      .trim()
      .is_empty()
    {
      return vec![];
    }
    let mut formals = Vec::new();
    for cap in self.formal_re.captures_iter(&text.into_bytes()) {
      if let Some(cap) = cap.ok() {
        if let Some(m) = cap.get(1) {
          let start_col = start_r.col + m.start();
          let end_col = start_r.col + m.end();
          if let Some(nm) = cap.get(2) {
            let name_start =
              ir::Position::new(start_r.col + nm.start(), start_r.line);
            let name_end =
              ir::Position::new(start_r.col + nm.end(), start_r.line);
            let name_loc = ir::Location::new(
              reader.filename.to_string_lossy(),
              ir::Range::new(name_start, name_end),
            );
            let name = ir::Name {
              location: name_loc,
              kind: ir::NameKind::Value(
                String::from_utf8_lossy(nm.as_bytes()).to_string(),
              ),
            };
            let start_formal = ir::Position::new(start_col, start_r.line);
            let end_formal = ir::Position::new(end_col, start_r.line);
            formals.push(ir::Formal {
              location: ir::Location::new(
                reader.filename.to_string_lossy(),
                ir::Range::new(start_formal, end_formal),
              ),
              name,
            });
          }
        }
      }
    }
    formals
  }

  fn _parse_define(&self, reader: &mut FileReader) -> Option<ir::IRNode> {
    let start_r = reader.position();
    let _ = reader.until("@");
    let (rloc, name_str) = reader.until_loc("( ").ok()?;
    let name_ir_loc = rdr_loc_to_ir(&rloc);
    let name = ir::Name {
      location: name_ir_loc,
      kind: ir::NameKind::Symbol(name_str),
    };
    let formals = self._parse_formals(reader);
    let stmts = self._parse_statements(reader);
    let end_r = reader.position();
    let loc = ir::Location::new(
      reader.filename.to_string_lossy(),
      ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
    );
    let def = ir::Define {
      location: loc,
      name,
      formals,
      statements: stmts,
    };
    Some(ir::IRNode::Function(ir::Function::Define(def)))
  }

  fn _parse_declare(&self, reader: &mut FileReader) -> Option<ir::IRNode> {
    let start_r = reader.position();
    let _ = reader.until("@");
    let (rloc, name_str) = reader.until_loc("( ").ok()?;
    let name = ir::Name {
      location: rdr_loc_to_ir(&rloc),
      kind: ir::NameKind::Symbol(name_str),
    };
    let formals = self._parse_formals(reader);
    let _ = reader.through("\n");
    let end_r = reader.position();
    let loc = ir::Location::new(
      reader.filename.to_string_lossy(),
      ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
    );
    let dec = ir::Declare {
      location: loc,
      name,
      formals,
    };
    Some(ir::IRNode::Function(ir::Function::Declare(dec)))
  }

  fn _parse_constant(&self, reader: &mut FileReader) -> Option<ir::IRNode> {
    let start_r = reader.position();
    let (rloc, name_str) = reader.until_loc(" =").ok()?;
    let name = ir::Name {
      location: rdr_loc_to_ir(&rloc),
      kind: ir::NameKind::Symbol(name_str),
    };
    let _ = reader.until("\n");
    let end_r = reader.position();
    let loc = ir::Location::new(
      reader.filename.to_string_lossy(),
      ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
    );
    let c = ir::Constant {
      location: loc,
      name,
    };
    Some(ir::IRNode::Constant(c))
  }

  fn _parse_attribute(&self, reader: &mut FileReader) -> Option<ir::IRNode> {
    let start_r = reader.position();
    let _ = reader.until("#");
    let (rloc, name_str) = reader.until_loc("= ").ok()?;
    let _ = reader.through("=");
    let _ = reader.until("{");
    let _body = self._read_curly_block(reader);
    let end_r = reader.position();
    let loc = ir::Location::new(
      reader.filename.to_string_lossy(),
      ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
    );
    let attr = ir::Attribute {
      location: loc,
      name: ir::Name {
        location: rdr_loc_to_ir(&rloc),
        kind: ir::NameKind::Attribute(name_str),
      },
    };
    Some(ir::IRNode::Attribute(attr))
  }

  fn _parse_metadata(&self, reader: &mut FileReader) -> Option<ir::IRNode> {
    let start_r = reader.position();
    let (rloc, name_str) = reader.until_loc("= ").ok()?;
    let _ = reader.through("=");
    let _ = reader.until("!d");
    if peek_str(reader, 3).unwrap_or_default() == "dis" {
      let _ = reader.until(" !");
      let _ = reader.skip(" \t");
    }
    if read_char(reader).unwrap_or('\0') != '!' {
      return None;
    }
    let _ = reader.skip(" \t");
    if peek_char(reader) == Some('{') {
      let _ = self._read_curly_block(reader);
    } else {
      let _ = self._read_block(reader, "(", ")");
    }
    let end_r = reader.position();
    let loc = ir::Location::new(
      reader.filename.to_string_lossy(),
      ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
    );
    let md = ir::Metadata {
      location: loc,
      name: ir::Name {
        location: rdr_loc_to_ir(&rloc),
        kind: ir::NameKind::Metadata(name_str),
      },
    };
    Some(ir::IRNode::Metadata(md))
  }

  fn _parse_percent_named(
    &self,
    reader: &mut FileReader,
  ) -> Option<ir::IRNode> {
    let start_r = reader.position();
    let (rloc, name_str) = reader.until_loc(" =").ok()?;
    let _ = reader.through("=");
    let _ = reader.skip(" \t");
    let ident = reader.until(" ").unwrap_or_default();
    if ident == "type" {
      let _ = self._read_curly_block(reader);
      let end_r = reader.position();
      let loc = ir::Location::new(
        reader.filename.to_string_lossy(),
        ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
      );
      let t = ir::TypeDefinition {
        location: loc,
        name: ir::Name {
          location: rdr_loc_to_ir(&rloc),
          kind: ir::NameKind::Value(name_str),
        },
      };
      return Some(ir::IRNode::TypeDefinition(t));
    } else {
      let _ = reader.until("\n");
      let end_r = reader.position();
      let loc = ir::Location::new(
        reader.filename.to_string_lossy(),
        ir::Range::new(rdr_pos_to_ir(&start_r), rdr_pos_to_ir(&end_r)),
      );
      let s = ir::Statement {
        location: loc.clone(),
        value: ir::Name {
          location: rdr_loc_to_ir(&rloc),
          kind: ir::NameKind::Value(name_str),
        },
      };
      return Some(ir::IRNode::Statement(s));

      // Some(ir::IRNode::Formal(ir::Formal { location: loc, name: ir::Name { location: rdr_loc_to_ir(&rloc), kind: ir::NameKind::Value(name_str) } }));
    }
  }
}

#[derive(Debug)]
pub struct NameParser {
  name_re: Regex,
}

impl NameParser {
  pub fn new() -> Self {
    Self {
      name_re: Regex::new(r"([%#@!])[a-zA-Z0-9_.]+").unwrap(),
    }
  }

  pub fn parse(&self, reader: &mut FileReader) -> Vec<ir::Name> {
    let mut names = Vec::new();
    let lines = reader.read_lines().unwrap_or_default();
    for (lineno, l) in lines.iter().enumerate() {
      for cap in self.name_re.captures_iter(l.as_bytes()) {
        if let Some(cap) = cap.ok() {
          if let Some(m) = cap.get(0) {
            let ty = &m.as_bytes()[0..1];
            let start = ir::Position::new(m.start(), lineno);
            let end = ir::Position::new(m.end(), lineno);
            let loc = ir::Location::new(
              reader.filename.to_string_lossy(),
              ir::Range::new(start, end),
            );
            let name = String::from_utf8_lossy(m.as_bytes()).to_string();
            let kind = match ty {
              b"%" => ir::NameKind::Value(name),
              b"#" => ir::NameKind::Attribute(name),
              b"@" => ir::NameKind::Symbol(name),
              b"!" => ir::NameKind::Metadata(name),
              _ => ir::NameKind::Bare(name),
            };
            names.push(ir::Name {
              location: loc,
              kind,
            });
          }
        }
      }
    }
    names
  }
}

#[cfg(test)]
#[path = "./test.rs"]
mod test;
