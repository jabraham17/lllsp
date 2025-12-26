use super::*;
use std::io::Write;

fn with_temp_file(content: &str) -> (tempfile::NamedTempFile, FileReader) {
  let mut tf = tempfile::NamedTempFile::new().unwrap();
  write!(tf, "{}", content).unwrap();
  let path = tf.path().to_path_buf();
  let fr = FileReader::open(path).unwrap();
  (tf, fr)
}

#[test]
fn test_read_and_peek() {
  let (_tf, mut r) = with_temp_file("abc\ndef");
  let p = r.peek(3).unwrap();
  assert_eq!(String::from_utf8_lossy(&p), "abc");
  let rd = r.read(3).unwrap();
  assert_eq!(String::from_utf8_lossy(&rd), "abc");
}
