from typing import Optional, Callable, Self
from dataclasses import dataclass, field




@dataclass
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


@dataclass
class Range:
    start: Position = field(default_factory=Position)
    end: Position = field(default_factory=Position)


@dataclass
class Location:
    filename: str = ""
    rng: Range = field(default_factory=Range)
