use std::collections::VecDeque;
use std::fs::File;
use std::io::{self, Read, Seek, SeekFrom};
use std::path::PathBuf;

use pcre2::bytes::Regex;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Position {
  pub col: usize,
  pub line: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Range {
  pub start: Position,
  pub end: Position,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Location {
  pub filename: PathBuf,
  pub range: Range,
}

#[derive(thiserror::Error, Debug)]
pub enum ReaderError {
  #[error("IO error: {0}")]
  Io(#[from] io::Error),
  #[error("EOF")]
  Eof,
  #[error("Regex error: {0}")]
  Regex(#[from] pcre2::Error),
}

pub struct FileReader {
  pub filename: PathBuf,
  fp: File,
  size: u64,
  stats: FileStats,
  peek_buf: VecDeque<u8>,
}

#[derive(Debug, Default)]
struct FileStats {
  line: usize,
  col: usize,
}

impl FileStats {
  fn count_bytes(&mut self, bytes: &[u8]) {
    for &b in bytes {
      if b == b'\n' {
        self.col = 0;
        self.line = self.line.saturating_add(1);
      } else {
        self.col = self.col.saturating_add(1);
      }
    }
  }
}

impl FileReader {
  pub fn open(filename: impl Into<PathBuf>) -> Result<Self, ReaderError> {
    let filename = filename.into();
    let mut fp = File::open(&filename)?;
    let size = fp.seek(SeekFrom::End(0))?;
    fp.seek(SeekFrom::Start(0))?;
    Ok(FileReader {
      filename,
      fp,
      size,
      stats: FileStats::default(),
      peek_buf: VecDeque::new(),
    })
  }

  pub fn reset(&mut self) -> Result<(), ReaderError> {
    self.fp.seek(SeekFrom::Start(0))?;
    self.stats = FileStats::default();
    self.peek_buf.clear();
    Ok(())
  }

  pub fn read_all(&mut self) -> Result<String, ReaderError> {
    let mut s = String::new();
    self.fp.seek(SeekFrom::Start(0))?;
    self.fp.read_to_string(&mut s)?;
    self.stats.count_bytes(s.as_bytes());
    Ok(s)
  }

  pub fn read_lines(&mut self) -> Result<Vec<String>, ReaderError> {
    let s = self.read_all()?;
    Ok(s.lines().map(|l| l.to_string() + "\n").collect())
  }

  pub fn tell(&mut self) -> Result<u64, ReaderError> {
    Ok(self.fp.seek(SeekFrom::Current(0))?)
  }

  pub fn read(&mut self, n: usize) -> Result<Vec<u8>, ReaderError> {
    let mut buf = vec![0u8; n];
    let read = self.fp.read(&mut buf)?;
    if read != n {
      return Err(ReaderError::Eof);
    }
    self.stats.count_bytes(&buf);
    Ok(buf)
  }

  pub fn peek(&mut self, n: usize) -> Result<Vec<u8>, ReaderError> {
    let pos = self.fp.seek(SeekFrom::Current(0))?;
    let mut buf = vec![0u8; n];
    let read = self.fp.read(&mut buf)?;
    self.fp.seek(SeekFrom::Start(pos))?;
    if read != n {
      return Err(ReaderError::Eof);
    }
    Ok(buf)
  }

  pub fn eof(&mut self) -> Result<bool, ReaderError> {
    let pos = self.fp.seek(SeekFrom::Current(0))?;
    Ok(pos >= self.size)
  }

  pub fn skip(&mut self, chars: &str) -> Result<String, ReaderError> {
    let mut read = Vec::new();
    loop {
      let mut b = [0u8; 1];
      let n = self.fp.read(&mut b)?;
      if n == 0 {
        break;
      }
      let c = b[0] as char;
      if !chars.contains(c) {
        let _ = self.fp.seek(SeekFrom::Current(-1))?;
        break;
      }
      read.push(b[0]);
    }
    self.stats.count_bytes(&read);
    Ok(String::from_utf8_lossy(&read).into_owned())
  }

  pub fn until(&mut self, chars: &str) -> Result<String, ReaderError> {
    let mut read = Vec::new();
    loop {
      let mut b = [0u8; 1];
      let n = self.fp.read(&mut b)?;
      if n == 0 {
        return Err(ReaderError::Eof);
      }
      let c = b[0] as char;
      if chars.contains(c) {
        self.fp.seek(SeekFrom::Current(-1))?;
        break;
      }
      read.push(b[0]);
    }
    self.stats.count_bytes(&read);
    Ok(String::from_utf8_lossy(&read).into_owned())
  }

  pub fn until_loc(
    &mut self,
    chars: &str,
  ) -> Result<(Location, String), ReaderError> {
    let start = self.position();
    let s = self.until(chars)?;
    let end = self.position();
    Ok((
      Location {
        filename: self.filename.clone(),
        range: Range { start, end },
      },
      s,
    ))
  }

  pub fn readr(&mut self, pat: &Regex) -> Result<String, ReaderError> {
    let mut read = Vec::new();
    let mut matched = false;
    loop {
      let mut b = [0u8; 1];
      let n = self.fp.read(&mut b)?;
      if n == 0 {
        return Err(ReaderError::Eof);
      }
      let candidate = {
        let mut t = read.clone();
        t.push(b[0]);
        String::from_utf8_lossy(&t).to_string()
      };
      // emulate Python's fullmatch behavior
      let m = pat.find(&candidate.as_bytes())?;
      if !matched
        && m.is_some()
        && m.unwrap().as_bytes().len() == candidate.len()
      {
        matched = true;
      } else if matched && m.is_none() {
        self.fp.seek(SeekFrom::Current(-1))?;
        break;
      }
      read.push(b[0]);
    }
    self.stats.count_bytes(&read);
    Ok(String::from_utf8_lossy(&read).into_owned())
  }

  pub fn readr_loc(
    &mut self,
    pat: &Regex,
  ) -> Result<(Location, String), ReaderError> {
    let start = self.position();
    let s = self.readr(pat)?;
    let end = self.position();
    Ok((
      Location {
        filename: self.filename.clone(),
        range: Range { start, end },
      },
      s,
    ))
  }

  pub fn through(&mut self, chars: &str) -> Result<String, ReaderError> {
    let mut read = Vec::new();
    loop {
      let mut b = [0u8; 1];
      let n = self.fp.read(&mut b)?;
      if n == 0 {
        return Err(ReaderError::Eof);
      }
      read.push(b[0]);
      let c = b[0] as char;
      if chars.contains(c) {
        break;
      }
    }
    self.stats.count_bytes(&read);
    Ok(String::from_utf8_lossy(&read).into_owned())
  }

  pub fn position(&self) -> Position {
    Position {
      col: self.stats.col,
      line: self.stats.line,
    }
  }
}

// Helper readers
pub fn peek_char(reader: &mut FileReader) -> Option<char> {
  if let Ok(v) = reader.peek(1) {
    if v.is_empty() {
      return None;
    }
    return Some(v[0] as char);
  }
  None
}

pub fn peek_str(reader: &mut FileReader, n: usize) -> Option<String> {
  if let Ok(v) = reader.peek(n) {
    return Some(String::from_utf8_lossy(&v).to_string());
  }
  None
}

pub fn read_char(reader: &mut FileReader) -> Option<char> {
  if let Ok(v) = reader.read(1) {
    if v.is_empty() {
      return None;
    }
    return Some(v[0] as char);
  }
  None
}

#[cfg(test)]
mod test;
