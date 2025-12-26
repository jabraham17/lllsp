use super::*;
use crate::parser::{IRParser, NameParser};
use crate::reader::FileReader;
use pretty_assertions::assert_eq;
use std::path::PathBuf;

fn resource(name: &str) -> FileReader {
  let cargo_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
  let resource_dir = cargo_dir.join("resources").join("test");
  let path = resource_dir.join(name);
  FileReader::open(path).unwrap()
}
fn ir_file(name: &str) -> FileReader {
  resource(format!("{}.ll", name).as_str())
}

fn load(reader: &mut FileReader) -> (Module, Vec<Name>) {
  let parser = IRParser::new();
  let m = parser.parse(reader);
  reader.reset().unwrap();
  let name_parser = NameParser::new();
  let names = name_parser.parse(reader);
  (m, names)
}

// convert human-like 1-based line number to 0-based line number (which is what Location uses)
fn ln(n: usize) -> usize {
  n - 1
}

#[test]
fn resolve_bar() {
  let mut reader = ir_file("simple");
  let (module, names) = load(&mut reader);

  // check that a given name resolves to a function named 'bar' thats defined on line 7
  let expected_checker = |n: &Name| {
    let resolved = module.resolve(n);
    assert!(resolved.is_some());
    let resolved = resolved.unwrap();
    match resolved {
      IRNode::Function(f) => match f {
        Function::Define(d) => {
          assert_eq!(d.name.basename(), "bar");
          assert_eq!(d.location.rng.start.line, ln(7));
        }
        _ => panic!("Expected Function::Define"),
      },
      _ => panic!("Expected IRNode::Function"),
    }
  };

  // check that bar can referenced in foo can be resolved to its definition
  let name_to_resolve = names
    .iter()
    .find(|n| n.basename() == "bar" && n.location.rng.start.line == ln(24))
    .unwrap();
  expected_checker(name_to_resolve);

  // check that we can resolve bar to itself
  let name_to_resolve = names
    .iter()
    .find(|n| n.basename() == "bar" && n.location.rng.start.line == ln(7))
    .unwrap();
  expected_checker(name_to_resolve);
}


#[test]
fn resolve_iaddr_for_bar() {
  let mut reader = ir_file("simple");
  let (module, names) = load(&mut reader);

  // check that i.addr on line 12 resolves to i.addr def on line 9
  let name_to_resolve = names
    .iter()
    .find(|n| n.basename() == "i.addr" && n.location.rng.start.line == ln(12))
    .unwrap();
  println!("Resolving {:?}", name_to_resolve);

  let resolved = module.resolve(name_to_resolve);
    assert!(resolved.is_some());
    let resolved = resolved.unwrap();
    match resolved {
      IRNode::Statement(s) => {
        assert_eq!(s.location.rng.start.line, ln(9));
        assert_eq!(s.value.basename(), "i.addr");
      }
      _ => panic!("Expected IRNode::Constant"),
    }
}
