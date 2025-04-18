from typing import Optional, Any, List, Tuple, Sequence
from dataclasses import dataclass, field
import io
import os
import abc
import re

import lllsp.ir as ir
from lllsp.ir.location import Location, Range, Position
from .reader import Reader, EOFException

import sys


def log(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


class IRParser:

    def __init__(self):
        self._value_name_regex = re.compile(r"^ *(%[a-zA-Z0-9_.]+)")
        self._label_regex = re.compile(r"^ *([a-zA-Z0-9_.]+:)")
        self._formal_regex = re.compile(
            r"\(?\s*([^,]*(%[a-zA-Z0-9_.]+)[^,()]*)(?=,|\))?"
        )

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
            c3 = reader.peek(3)
            if c3 == "def":
                return self._parse_define(reader)
            elif c3 == "dec":
                return self._parse_declare(reader)
            else:
                # TODO: what should we do in this case? some kind of warning?
                reader.through("\n")
                return None
        elif c == "%":
            return self._parse_percent_named(reader)
        elif c == "@":
            return self._parse_constant(reader)
        elif c == "a":
            return self._parse_attribute(reader)
        elif c == "!":
            return self._parse_metadata(reader)
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
        return self._read_block(reader, "{", "}")

    def _read_block(self, reader: Reader, start: str, end: str) -> str:
        text = ""
        text += reader.through(start)
        pairs = 1
        while True:
            text += reader.until(start + end)
            n = reader.read()
            text += n
            if n == start:
                pairs += 1
            else:
                pairs -= 1
            if pairs == 0:
                break
        return text

    def _parse_statements(
        self, reader: Reader
    ) -> List[ir.Statement | ir.Label]:
        # parse all statements inside of curly braces
        start = reader.position()  # used to determine line info
        text = self._read_curly_block(reader)
        # split text based on newlines
        lines = text.splitlines()
        statements = []
        for lineno, l in enumerate(lines):
            if m := re.match(self._value_name_regex, l):
                start_col = (
                    start.column + m.start(1) if lineno == 0 else m.start(1)
                )
                name_end_col = (
                    start.column + m.end(1) if lineno == 0 else m.end(1)
                )
                end_col = start.column + len(l) if lineno == 0 else len(l)
                name_start = Position(start_col, start.line + lineno)
                name_end = Position(name_end_col, start.line + lineno)
                stmt_end = Position(end_col, start.line + lineno)
                name = ir.ValueName(
                    Location(reader.filename, Range(name_start, name_end)),
                    m.group(1),
                )
                statements.append(
                    ir.StatementWithValue(
                        Location(reader.filename, Range(name_start, stmt_end)),
                        name,
                    )
                )
            elif m := re.match(self._label_regex, l):
                start_col = (
                    start.column + m.start(1) if lineno == 0 else m.start(1)
                )
                name_end_col = (
                    start.column + m.end(1) if lineno == 0 else m.end(1)
                )
                name_start = Position(start_col, start.line + lineno)
                name_end = Position(name_end_col, start.line + lineno)
                label = ir.Label(
                    Location(reader.filename, Range(name_start, name_end)),
                    m.group(1),
                )
                statements.append(label)
            else:
                # for now, no need to handle statements that don't have values
                pass
        return statements

    def _parse_formals(self, reader: Reader) -> List[ir.Formal]:
        # parse everything in the ()
        start = reader.position()  # used to determine line info
        text = self._read_block(reader, "(", ")")
        if len(text.strip().removeprefix("(").removesuffix(")").strip()) == 0:
            return []
        # split based on ','
        # TODO: what if there are other commands in an arg attribute?

        formals = []
        for m in re.finditer(self._formal_regex, text):
            start_col = start.column + m.start(1)
            end_col = start.column + m.end(1)
            name_start_col = start.column + m.start(2)
            name_end_col = start.column + m.end(2)
            
            name_start = Position(name_start_col, start.line)
            name_end = Position(name_end_col, start.line)
            name = ir.ValueName(
                Location(reader.filename, Range(name_start, name_end)),
                m.group(2),
            )
            start_formal = Position(start_col, start.line)
            end_formal = Position(end_col, start.line)
            formals.append(
                ir.Formal(
                    Location(
                        reader.filename, Range(start_formal, end_formal)
                    ),
                    name,
                )
            )
        return formals

    def _parse_define(self, reader: Reader) -> Optional[ir.Define]:
        start = reader.position()
        reader.until("@")

        name = ir.SymbolName(*reader.until_loc("( "))

        formals = self._parse_formals(reader)
        stmts = self._parse_statements(reader)

        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        d = ir.Define(loc, name, formals, stmts)
        return d

    def _parse_declare(self, reader: Reader) -> Optional[ir.Declare]:
        start = reader.position()
        reader.until("@")

        name = ir.SymbolName(*reader.until_loc("( "))

        # TODO: this does not handle multiline declare
        formals = self._parse_formals(reader)
        reader.through("\n")

        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        d = ir.Declare(loc, name, formals)
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

    def _parse_attribute(self, reader: Reader) -> Optional[ir.Attribute]:
        start = reader.position()
        reader.until("#")

        name = ir.AttributeName(*reader.until_loc("= "))
        reader.through("=")
        reader.until("{")

        body = self._read_curly_block(reader)

        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        return ir.Attribute(loc, name)

    def _parse_metadata(self, reader: Reader) -> Optional[ir.Metadata]:
        start = reader.position()

        name = ir.MetadataName(*reader.until_loc("= "))
        reader.through("=")
        reader.until("!d")
        if reader.peek(3) == "dis":
            # get rid of the distinct by reading to space
            reader.until(" !")
            reader.skip(" \t")
        # we now should have "!"
        if reader.read() != "!":
            return None
        reader.skip(" \t")
        if reader.peek() == "{":
            self._read_curly_block(reader)
        else:
            # we assume its a paren-like thing
            self._read_block(reader, "(", ")")

        end = reader.position()
        loc = Location(reader.filename, Range(start, end))
        return ir.Metadata(loc, name)

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

    def parse(self, reader: Reader) -> List[ir.Name]:
        names: List[ir.Name] = []
        lines = reader.readlines()
        # TODO: this doesn't handle ':'
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
