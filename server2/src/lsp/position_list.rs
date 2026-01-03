use tower_lsp::lsp_types::{Position, Range};

/// A data structure that keeps elements ordered by their start position and
/// exposes segment queries.
#[derive(Debug)]
pub struct PositionList<EltT: Clone> {
  pub get_range: fn(&EltT) -> Range,
  pub elts: Vec<EltT>,
  pub segments: Vec<(Position, Option<usize>, i32)>,
}

impl<EltT: Clone> PositionList<EltT> {
  pub fn new(get_range: fn(&EltT) -> Range) -> Self {
    Self {
      get_range,
      elts: Vec::new(),
      segments: Vec::new(),
    }
  }

  fn get_negated_pos(pos: &Position) -> (i32, i32) {
    (-(pos.line as i32), -(pos.character as i32))
  }

  fn push_segment(
    into: &mut Vec<(Position, Option<usize>, i32)>,
    pos: Position,
    elt: Option<usize>,
    idx: i32,
  ) {
    while into.last().map(|x| x.0 == pos).unwrap_or(false) {
      into.pop();
    }
    into.push((pos, elt, idx));
  }

  fn elements_to_segments_from(
    elts: &[EltT],
    into: &mut Vec<(Position, Option<usize>, i32)>,
    get_range: fn(&EltT) -> Range,
  ) {
    let mut ongoing: Vec<(Position, usize, i32)> = Vec::new();

    for (idx, elt) in elts.iter().enumerate() {
      let rng = get_range(elt);

      while let Some((pos, _elt, _i)) = ongoing.last() {
        if *pos <= rng.start {
          let pos = ongoing.pop().unwrap().0;
          if let Some((_, v, i)) = ongoing.last() {
            Self::push_segment(into, pos, Some(*v), *i);
          } else {
            Self::push_segment(into, pos, None, -1);
          }
        } else {
          break;
        }
      }

      Self::push_segment(into, rng.start.clone(), Some(idx), idx as i32);

      ongoing.retain(|(p, _v, _i)| *p > rng.end);

      // insert in descending order by end
      let mut insert_idx = ongoing.len();
      for (j, (p, _, _)) in ongoing.iter().enumerate() {
        if Self::get_negated_pos(&rng.end) < Self::get_negated_pos(p) {
          insert_idx = j;
          break;
        }
      }
      ongoing.insert(insert_idx, (rng.end, idx, insert_idx as i32));
    }

    while let Some((pos, _v, _i)) = ongoing.pop() {
      if let Some((_, v, i)) = ongoing.last() {
        Self::push_segment(into, pos, Some(*v), *i);
      } else {
        Self::push_segment(into, pos, None, -1);
      }
    }
  }

  pub fn _rebuild_segments(&mut self) {
    self.segments.clear();
    Self::elements_to_segments_from(
      &self.elts,
      &mut self.segments,
      self.get_range,
    );
  }

  pub fn sort(&mut self) {
    self.elts.sort_by_key(|e| (self.get_range)(e).start.clone());
    self._rebuild_segments();
  }

  pub fn append(&mut self, elt: EltT) {
    self.elts.push(elt);
  }

  fn get_elt_range(&self, rng: &Range) -> (usize, usize) {
    let start = self
      .elts
      .binary_search_by_key(&rng.start, |x| (self.get_range)(x).start.clone())
      .unwrap_or_else(|x| x);
    let end = self
      .elts
      .binary_search_by_key(&rng.end, |x| (self.get_range)(x).start.clone())
      .unwrap_or_else(|x| x);
    (start, end)
  }

  fn get_segment_range(&self, rng: &Range) -> (usize, usize) {
    let start = self
      .segments
      .binary_search_by_key(&rng.start, |x| x.0.clone())
      .unwrap_or_else(|x| x);
    let end = self
      .segments
      .binary_search_by_key(&rng.end, |x| x.0.clone())
      .unwrap_or_else(|x| x);
    (start, end)
  }

  pub fn clear_range(&mut self, rng: &Range) {
    let (s, e) = self.get_elt_range(rng);
    self.elts.splice(s..e, std::iter::empty());
    self._update_segments(rng, &[]);
  }

  fn _update_segments(
    &mut self,
    rng: &Range,
    new_segments: &[(Position, Option<usize>, i32)],
  ) {
    let filtered: Vec<(Position, Option<usize>, i32)> = new_segments
      .iter()
      .cloned()
      .filter(|seg| rng.start <= seg.0 && seg.0 < rng.end)
      .collect();
    let (seg_start, seg_end) = self.get_segment_range(rng);

    let (after_value, after_idx) = if seg_end > 0 {
      (self.segments[seg_end - 1].1, self.segments[seg_end - 1].2)
    } else {
      (None, -1)
    };

    let mut to_insert: Vec<(Position, Option<usize>, i32)> = Vec::new();
    if filtered.is_empty() || filtered[0].0 > rng.start {
      to_insert.push((rng.start.clone(), None, -1));
    }
    to_insert.extend(filtered.into_iter());
    if seg_end >= self.segments.len() || self.segments[seg_end].0 > rng.end {
      to_insert.push((rng.end.clone(), after_value, after_idx));
    }

    self.segments.splice(seg_start..seg_end, to_insert);
  }

  pub fn _set_range(&mut self, rng: &Range, elts: Vec<EltT>) {
    let (start, end) = self.get_elt_range(rng);
    self.elts.splice(start..end, elts.clone());
    let mut elt_segs: Vec<(Position, Option<usize>, i32)> = Vec::new();
    Self::elements_to_segments_from(&elts, &mut elt_segs, self.get_range);
    self._update_segments(rng, &elt_segs);
  }

  pub fn overwrite(&mut self, elt: EltT) {
    let rng = (self.get_range)(&elt);
    self._set_range(&rng, vec![elt]);
  }

  pub fn clear(&mut self) {
    self.elts.clear();
    self.segments.clear();
  }

  pub fn find(&self, pos: &Position) -> Option<usize> {
    let idx = self
      .segments
      .binary_search_by_key(pos, |x| x.0.clone())
      .unwrap_or_else(|x| x);
    if idx >= 1 {
      if let Some(val) = self.segments[idx - 1].1 {
        return Some(val);
      }
    }
    if idx < self.segments.len() && self.segments[idx].0 == *pos {
      return self.segments[idx].1;
    }
    None
  }

  pub fn range(&self, rng: &Range) -> Vec<usize> {
    let (start, end) = self.get_segment_range(rng);
    self.segments[start..end]
      .iter()
      .filter_map(|x| x.1)
      .collect()
  }
}

#[cfg(test)]
#[path = "./position_list_test.rs"]
mod position_list_test;
