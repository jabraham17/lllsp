# copied and modified from https://github.com/chapel-lang/chapel/blob/main/tools/chpl-language-server/src/chpl-language-server.py
#
# Copyright 2024-2024 Hewlett Packard Enterprise Development LP
# Other additional copyright holders may be indicated within.
#
# The entirety of this work is licensed under the Apache License,
# Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.
#
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, TypeVar, Callable, Generic, Self
from bisect import bisect_left, bisect_right
from lsprotocol.types import Position, Range

EltT = TypeVar("EltT")

@dataclass
class PositionList(Generic[EltT]):
    get_range: Callable[[EltT], Range]
    """
    The function that retrieves the range of an element in the list.
    """

    elts: List[EltT] = field(default_factory=list)
    """
    A list of elements in the list, sorted by their start positions. Example
    list of items:

        |------------| A
               |-------------| B
                       |--| C
                                  |---------| D
    """

    segments: List[Tuple[Position, Optional[EltT], int]] = field(
        default_factory=list
    )
    """
    A flattened representation of the list of elements, where each element
    represents the beginning of a new item that continues until the next
    element in the list. The following segments are equivalent to the above
    list of items:

        |------|-------|--|--|----|---------|
         A      B       C  B  None D

    Note that 'B' occurs twice, and there's a 'None' in the middle. The
    'None' serves to clear the segment that was started by 'B'.

    This representation makes it easy to find the exact item at a given
    position in logarithmic time.
    """

    def _elements_to_segments(
        self, elts: List[EltT], into: List[Tuple[Position, Optional[EltT], int]]
    ):
        # A list of not-yet-closed segments, sorted descending by their end positions
        # (so that we can pop the last one to close it).
        ongoing: List[Tuple[Position, EltT, int]] = []

        # To be able to insert ongoing segments in descending order.
        def get_negated_pos(pos: Position):
            return (-pos.line, -pos.character)

        def push_segment(pos: Position, elt: Optional[EltT], idx: int):
            # Don't create duplicate segments for the same position.
            while len(into) > 0 and into[-1][0] == pos:
                into.pop()
            into.append((pos, elt, idx))

        # Close any ongoing segments that we need to close.
        #
        # When we close the segment, we switch to the one underneath.
        def push_segment_from_ongoing(pos: Position):
            # If there's a segment underneath, restart it.
            if len(ongoing) > 0:
                push_segment(pos, ongoing[-1][1], ongoing[-1][2])
            # No segment underneath; just clear the current one.
            else:
                push_segment(pos, None, -1)

        for idx, elt in enumerate(elts):
            rng = self.get_range(elt)

            # Close segments that end before this element starts.
            while len(ongoing) > 0 and ongoing[-1][0] <= rng.start:
                pos, _, _ = ongoing.pop()

                # We maintain the invariant that no ongoing segments end
                # in the same place, so the segment underneath at the top after
                # popping is the one we want to continue.
                push_segment_from_ongoing(pos)

            # Start a new segment for this element.
            push_segment(rng.start, elt, idx)

            # Remove all segments from 'ongoing' that end before this element.
            ongoing = [x for x in ongoing if x[0] > rng.end]

            # Add this element to 'ongoing' so that we can close or continue it later.
            idx = bisect_right(
                ongoing,
                get_negated_pos(rng.end),
                key=lambda x: get_negated_pos(x[0]),
            )
            ongoing.insert(idx, (rng.end, elt, idx))

        # Close all remaining segments.
        while len(ongoing) > 0:
            pos, _, _ = ongoing.pop()
            push_segment_from_ongoing(pos)

    def _rebuild_segments(self):
        self.segments.clear()
        self._elements_to_segments(self.elts, self.segments)

    def sort(self):
        """
        Re-ensure this segment list has its invariants upheld, by sorting
        the list of items and re-building the segments.
        """
        self.elts.sort(key=lambda x: self.get_range(x).start)
        self._rebuild_segments()

    def append(self, elt: EltT):
        self.elts.append(elt)

    def _get_elt_range(self, rng: Range):
        start = bisect_left(
            self.elts, rng.start, key=lambda x: self.get_range(x).start
        )
        end = bisect_right(
            self.elts, rng.end, key=lambda x: self.get_range(x).start
        )
        return (start, end)

    def _get_segment_range(self, rng: Range):
        start = bisect_left(self.segments, rng.start, key=lambda x: x[0])
        end = bisect_left(self.segments, rng.end, key=lambda x: x[0])
        return (start, end)

    def _update_segments(
        self, rng: Range, new_segments: List[Tuple[Position, EltT, int]]
    ):
        new_segments = [
            seg for seg in new_segments if rng.start <= seg[0] < rng.end
        ]

        seg_start, seg_end = self._get_segment_range(rng)
        if seg_end > 0:
            after_value, after_idx = self.segments[seg_end - 1][1:]
        else:
            after_value, after_idx = None, -1

        to_insert = []

        # If the segments start halfway through the range, insert a new segment,
        # ensure that between rng.start and the start of the first segment, there
        # is a 'None' segment to clear the preceding segment.
        if len(new_segments) == 0 or new_segments[0][0] > rng.start:
            to_insert.append((rng.start, None, -1))

        # Insert the new segments.
        to_insert.extend(new_segments)

        # Resume whatever was continuing after the range, unless the next
        # segment starts right after the range.
        if seg_end >= len(self.segments) or self.segments[seg_end][0] > rng.end:
            to_insert.append((rng.end, after_value, after_idx))

        self.segments[seg_start:seg_end] = to_insert

    def clear_range(self, rng: Range):
        elt_start, elt_end = self._get_elt_range(rng)
        self.elts[elt_start:elt_end] = []

        self._update_segments(rng, [])

    def _set_range(self, rng: Range, elts: List[EltT]):
        start, end = self._get_elt_range(rng)
        self.elts[start:end] = elts

        elt_segs = []
        self._elements_to_segments(elts, elt_segs)
        self._update_segments(rng, elt_segs)

    def overwrite(self, elt: EltT):
        self._set_range(self.get_range(elt), [elt])

    def overwrite_range(self, rng: Range, other: Self):
        other_start, other_end = other._get_elt_range(rng)
        self._set_range(rng, other.elts[other_start:other_end])

    def clear(self):
        self.elts.clear()
        self.segments.clear()

    def find(self, pos: Position) -> Optional[EltT]:
        idx = bisect_left(self.segments, pos, key=lambda x: x[0])

        if idx >= 1 and self.segments[idx - 1][1] is not None:
            return self.segments[idx - 1][1]

        # In some cases, we may be on the boundary between two segments.
        # In this case, the next segment's start position is the same as
        # the current position, and we should return the next segment.
        if idx < len(self.segments) and self.segments[idx][0] == pos:
            return self.segments[idx][1]

        return None

    def range(self, rng: Range) -> List[EltT]:
        start, end = self._get_segment_range(rng)
        return [x[1] for x in self.segments[start:end] if x[1] is not None]
