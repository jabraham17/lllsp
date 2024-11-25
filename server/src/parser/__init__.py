from typing import Optional, Any, List, Tuple, Sequence
from dataclasses import dataclass, field
import io
import os
import abc
import re

import ir
from ir.location import Location, Range, Position
from .reader import Reader, EOFException

import sys
def log(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


class IRParser:

    def __init__(self):
        self._value_name_regex = re.compile(r"^ *(%[a-zA-Z0-9_.]+)")
        self._label_regex = re.compile(r"^ *([a-zA-Z0-9_.]+:)")

    def parse(self, reader: Reader) -> ir.Module:

        loc = Location()
        mod = ir.Module(loc)

        start = reader.position()
        while not reader.eof():
            if i := self.parse_one(reader):
                mod.add(i)
        end = reader.position()
        # patch the location and return
        mod.location = Location(reader.filename, Range(start, end))
        return mod


    def parse_one(self, reader: Reader):
        reader.skip(" \t")
        c = reader.peek()
        if c == ";":
            self._parse_comment(reader)
        elif c == "s" or c == "t":
            # TODO actually implement
            reader.through("\n")
            return None
        elif c == "d":
            c2 = reader.peek(3)
            if c2 == "def":
                return self._parse_define(reader)
            elif c2 == "dec":
                return self._parse_declare(reader)
            else:
                # TODO: what should we do in this case? some kind of warning?
                reader.through("\n")
                return None
        elif c == "%":
            return self._parse_percent_named(reader)
        elif c == "@":
            return self._parse_constant(reader)
        else:
            # TODO : implement
            reader.through("\n")
            return None


    def _parse_comment(self, reader: Reader):
        c = reader.read()
        if c != ";":
            raise ValueError("not a comment")
        # read until newline
        reader.through("\n")

    def _read_curly_block(self, reader: Reader) -> str:
        text = ""
        text += reader.through("{")
        pairs = 1
        while True:
            text += reader.until("}{")
            n = reader.read()
            text += n
            if n == "{":
                pairs += 1
            else:
                pairs -= 1
            if pairs == 0:
                break
        return text

    def _parse_statements(self, reader: Reader) -> List[ir.Statement | ir.Label]:
        # parse all statements inside of curly braces
        start = reader.position() # used to determine line info
        text = self._read_curly_block(reader)
        # split text based on newlines
        lines = text.splitlines()
        statements = []
        for lineno, l in enumerate(lines):
            if m := re.match(self._value_name_regex, l):
                start_col = start.column + m.start(1) if lineno == 0 else m.start(1)
                name_end_col = start.column + m.end(1) if lineno == 0 else m.end(1)
                end_col = start.column + len(l) if lineno == 0 else len(l)
                name_start = Position(start_col, start.line+lineno)
                name_end = Position(name_end_col, start.line+lineno)
                stmt_end = Position(end_col, start.line+lineno)
                name = ir.ValueName(Location(reader.filename, Range(name_start, name_end)), m.group(1))
                statements.append(ir.StatementWithValue(Location(reader.filename, Range(name_start, stmt_end)), name))
            elif m := re.match(self._label_regex, l):
                start_col = start.column + m.start(1) if lineno == 0 else m.start(1)
                name_end_col = start.column + m.end(1) if lineno == 0 else m.end(1)
                name_start = Position(start_col, start.line+lineno)
                name_end = Position(name_end_col, start.line+lineno)
                label = ir.Label(Location(reader.filename, Range(name_start, name_end)), m.group(1))
                statements.append(label)
            else:
                # for now, no need to handle statements that don't have values
                pass
        return statements

    def _parse_define(self, reader: Reader) -> Optional[ir.Define]:
        start = reader.position()
        reader.until("@")

        name = ir.SymbolName(*reader.until_loc("( "))

        # TODO parse args
        reader.through(")")
        stmts = self._parse_statements(reader)

        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        d = ir.Define(loc, name, stmts)
        return d
    
    def _parse_declare(self, reader: Reader) -> Optional[ir.Declare]:
        start = reader.position()
        reader.until("@")

        name = ir.SymbolName(*reader.until_loc("( "))
        
        # TODO: this does not handle multiline declare
        reader.through("\n")


        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        d = ir.Declare(loc, name)
        return d

    def _parse_constant(self, reader: Reader) -> Optional[ir.Constant]:
        start = reader.position()
        name = ir.SymbolName(*reader.until_loc(" ="))

        # TODO: technically there can be newlines, which aren't handled here
        reader.until("\n")

        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        c = ir.Constant(loc, name)
        return c

    def _parse_percent_named(self, reader: Reader) -> Optional[ir.IR]:
        start = reader.position()
        name = ir.ValueName(*reader.until_loc(" ="))
        
        # consume =
        reader.through("=")
        reader.skip(" \t")

        # read the next thing
        ident = reader.until(" ")
        if ident == "type":
            body = self._read_curly_block(reader)
            end = reader.position()
            loc = Location(reader.filename, Range(start, end))
            t = ir.TypeDefinition(loc, name)
            return t
        else:
            # the rest of the line is the statement
            reader.until("\n")
            end = reader.position()
            loc = Location(reader.filename, Range(start, end))
            s = ir.StatementWithValue(loc, name)
            return s



class NameParser:
    """
    Parse and extract everything that looks like a name
    """

    def __init__(self):
        self._name_regex = re.compile(r"([%#@!])[a-zA-Z0-9_.]+")

    # this version is too slow
    # def parse(self, reader: Reader) -> List[ir.Name]:
    #     names: List[ir.Name] = []
    #     while not reader.eof():
    #         # TODO: this does not handle strings yet

    #         try:
    #             text = reader.until("%#@:!")
    #         except EOFException:
    #             break
    #         c = reader.peek()
    #         if c == ":":
    #             # if its a ":", we need to go back
    #             # TODO: unimp
    #             reader.read(1)
    #         else:
    #             name_types = {
    #                 "%": ir.ValueName,
    #                 "#": ir.AttributeName,
    #                 "@": ir.SymbolName,
    #                 "!": ir.MetadataName,
    #             }
    #             ty = name_types[c]
    #             n = ty(*reader.readr_loc(self._name_regex))
    #             names.append(n)
    #     return names

    def parse(self, reader: Reader) -> List[ir.Name]:
        names: List[ir.Name] = []
        lines = reader.readlines()
        name_types = {
                    "%": ir.ValueName,
                    "#": ir.AttributeName,
                    "@": ir.SymbolName,
                    "!": ir.MetadataName,
                }
        for lineno, l in enumerate(lines):
            for m in re.finditer(self._name_regex, l):
                ty = name_types[m.group(1)]
                start = Position(m.start(), lineno)
                end = Position(m.end(), lineno)
                loc = Location(reader.filename, Range(start, end))
                names.append(ty(loc, m.group(0)))
        return names



