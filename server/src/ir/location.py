from typing import Optional, Callable, Self
from dataclasses import dataclass, field
import functools



@dataclass
@functools.total_ordering
class Position:
    column: int = 0
    line: int = 0

    def mod_col(self, modifier: Callable[[int], int] | int) -> Self:
        if isinstance(modifier, int):
            self.column += modifier
        else:
            self.column = modifier(self.column)
        return self
    def mod_line(self, modifier: Callable[[int], int] | int) -> Self:
        if isinstance(modifier, int):
            self.line += modifier
        else:
            self.line = modifier(self.line)
        return self
    
    def __eq__(self, o: Self) -> bool:
        if not isinstance(o, Position):
            return NotImplemented
        return (self.line, self.column) == (o.line, o.column)

    def __gt__(self, o: Self) -> bool:
        if not isinstance(o, Position):
            return NotImplemented
        return (self.line, self.column) > (o.line, o.column)


@dataclass
class Range:
    start: Position = field(default_factory=Position)
    end: Position = field(default_factory=Position)

    def __contains__(self, o: Self | Position) -> bool:
        if isinstance(o, Range):
            return o.start >= self.start and o.end <= self.end
        elif isinstance(o, Position):
            return o >= self.start and o <= self.end
        else:
            return NotImplemented



@dataclass
class Location:
    filename: str = ""
    rng: Range = field(default_factory=Range)
