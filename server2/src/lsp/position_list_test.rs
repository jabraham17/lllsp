use super::*;

#[derive(Clone)]
struct Item {
  start: Position,
  end: Position,
  id: usize,
}

fn get_range(it: &Item) -> Range {
  Range::new(it.start.clone(), it.end.clone())
}

#[test]
fn basic_segments_and_find() {
  let mut pl = PositionList::new(get_range);
  pl.append(Item {
    start: Position::new(0, 0),
    end: Position::new(0, 5),
    id: 1,
  });
  pl.append(Item {
    start: Position::new(0, 2),
    end: Position::new(0, 9),
    id: 2,
  });
  pl.append(Item {
    start: Position::new(0, 5),
    end: Position::new(0, 6),
    id: 3,
  });
  pl.sort();
  // find at position 0,0 -> should be first element index 0
  let found = pl.find(&Position::new(0, 0)).unwrap();
  assert_eq!(found, 0);
  // range covering start..end should return some indices
  let r = Range::new(Position::new(0, 0), Position::new(0, 10));
  let ids = pl.range(&r);
  assert!(!ids.is_empty());
}
