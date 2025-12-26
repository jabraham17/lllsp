use super::*;
use crate::reader::FileReader;
use pretty_assertions::assert_eq;
use std::io::Write;

fn with_temp_file(content: &str) -> (tempfile::NamedTempFile, FileReader) {
  let mut tf = tempfile::NamedTempFile::new().unwrap();
  write!(tf, "{}", content).unwrap();
  let path = tf.path().to_path_buf();
  let fr = FileReader::open(path).unwrap();
  (tf, fr)
}

#[test]
fn test_simple_ir() {
  let (_tf, mut r) = with_temp_file(
    r#"
define i32 @add(i32 %a, i32 %b) {
  %result = add i32 %a, %b
  ret i32 %result
}
        "#,
  );

  let p = IRParser::new();
  let ir = p.parse(&mut r);
  assert!(ir.functions.len() == 1);
  let f = &ir.functions[0];
  println!("{:#?}", f);
  match f {
    ir::Function::Define(d) => {
      assert_eq!(d.name.basename(), "add");
      assert_eq!(d.formals.len(), 2);
      assert_eq!(d.statements.len(), 1); // ret doesn't count as statement
    }
    _ => panic!("Expected function definition"),
  }

  r.reset()
    .unwrap_or_else(|e| panic!("Failed to reset reader: {}", e));
  let p = NameParser::new();
  let names = p.parse(&mut r);
  assert_eq!(names.len(), 7);
  assert_eq!(names[0].basename(), "add");
  assert_eq!(names[1].basename(), "a");
  assert_eq!(names[2].basename(), "b");
  assert_eq!(names[3].basename(), "result");
  assert_eq!(names[4].basename(), "a");
  assert_eq!(names[5].basename(), "b");
  assert_eq!(names[6].basename(), "result");
}
