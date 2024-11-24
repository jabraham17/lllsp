from typing import Optional, Any, List
from dataclasses import dataclass, field
import io
import os
import abc

import ir
from ir.location import Location, Range
from .reader import Reader

import sys
def log(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


class IRParser:

    def __init__(self):
        pass

    def parse(self, reader: Reader) -> List[ir.IR]:
        elements = []

        while not reader.eof():
            if i := self.parse_one(reader):
                elements.append(i)
        return elements

    def parse_one(self, reader: Reader) -> Optional[ir.IR]:
        reader.skip(" \t")
        c = reader.peek()
        log(f"parsing {c}")
        if c == ";":
            self._parse_comment(reader)
            return None
        elif c == "s" or c == "t":
            # TODO actually implelemt
            reader.through("\n")
            return None
        elif c == "d":
            c2 = reader.peek(2)
            if c2 == "de":
                return self._parse_define(reader)
            else:
                assert False, "unimp"
        elif c == "%":
            return self._parse_percent_named(reader)
        else:
            # TODO : impelemetn
            reader.through("\n")
            # assert False, "unimp"


    def _parse_comment(self, reader: Reader):
        c = reader.read()
        if c != ";":
            raise ValueError("not a comment")
        # read until newline
        reader.through("\n")

    def _parse_define(self, reader: Reader) -> Optional[ir.Define]:
        start = reader.position()
        reader.until("@")

        name = ir.FunctionName(*reader.until_loc("( "))

        # TODO parse args, for now just parse to end of curly brace
        reader.through(")")
        reader.through("{")
        pairs = 1
        while True:
            reader.until("}{")
            n = reader.read()
            if n == "{":
                pairs += 1
            else:
                pairs -= 1
            if pairs == 0:
                break
        
        end = reader.position()

        loc = Location(reader.filename, Range(start, end))
        d = ir.Define(loc, name, [])
        return d

    def _parse_percent_named(self, reader: Reader) -> Optional[ir.IR]:
        start = reader.position()
        name = ir.ValueName(*reader.until_loc(" ="))
        
        # consume =
        reader.through("=")
        reader.skip(" \t")

        # read the next thing
        ident = reader.until(" ")
        if ident == "type":
            # assert False, "unimp"
            # TODO
            reader.through("\n")
            return None
        else:
            # the rest of the line is the statement
            reader.until("\n")
            end = reader.position()
            loc = Location(reader.filename, Range(start, end))
            s = ir.StatementWithValue(loc, name)
            return s




