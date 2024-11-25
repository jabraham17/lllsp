
from typing import Optional, Any, List, Tuple
from dataclasses import dataclass, field
import io
import os
import re
from ir.location import Position, Location, Range




# class FileStats:
#     def __init__(self):
#         self.num_chars_read = 0
#         self.num_newlines_read = 0

#     def count(self, s: str):
#         self.num_chars_read += len(s)
#         self.count_newlines(s)

#     def count_newlines(self, s: str):
#         self.num_newlines_read += s.count('\n')
    
#     def position(self) -> Position:


# @dataclass
# class TextReader:
#     text: str
#     index: int = field(default=0, init=False)
#     stats: FileStats

#     @property
#     def filename(self) -> str:
#         return "root.ll"

#     def read(self, n=1) -> str:
#         ret = self.peek(n)
#         self.index += n
#         self.stats.count(ret)
#         return ret

#     def peek(self, n=1) -> str:
#         if self.index + n >= len(self.text):
#             raise ValueError("EOF")
#         return self.text[self.index : self.index + n]

#     def eof(self) -> bool:
#         return self.index < len(self.text)

#     def skip(self, chars=" \t\n"):
#         read = 0
#         while True:
#             if self.index + read >= len(self.text):
#                 break
#             if self.text[self.index + read] not in chars:
#                 break
#             if self.text[self.index + read] == "\n":
#                 self.stats.num_newlines_read += 1
#             read += 1
#         self.index += read
#         self.stats.num_chars_read += read
#         return read

#     def until(self, char: str) -> str:
#         read = 0
#         while True:
#             if self.index + read >= len(self.text):
#                 raise ValueError("char not found")
#             if self.text[self.index + read] == char:
#                 break
#             read += 1
#         s = self.text[self.index:self.index+read]
#         self.index += read
#         self.stats.count(s)
#         return s

#     def through(self, char: str):
#         s = self.until(char)
#         extra = self.text[self.index]
#         self.stats.count(extra)
#         s += s
#         self.index += 1
#         return s

    

class EOFException(Exception):
    pass

class Peeker:

    def __init__(self, fp):
        self.fp = fp
        self.tell = 0

    def __enter__(self):
        self.tell = self.fp.tell()
        return self

    def __exit__(self, *args):
        self.fp.seek(self.tell, os.SEEK_SET)

class FileStats:
    def __init__(self):
        self.line = 0
        self.col = 0
    
    def count(self, s: str):
        for c in s:
            if c == "\n":
                self.col = 0
                self.line += 1
            else:
                self.col += 1


class FileReader:
    def __init__(self, filename: str):
        self.filename = filename
        
    def open(self):
        self._fp = open(self.filename, "r")
        self._stats = FileStats()
        with Peeker(self._fp):
            self._fp.seek(0, os.SEEK_END)
            self._size = self._fp.tell()
    
    def close(self):
        self._fp.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
    
    def readall(self) -> str:
        return self._fp.read()

    def readlines(self) -> List[str]:
        return self._fp.readlines()

    def read(self, n=1) -> str:
        ret = self._fp.read(n)
        if len(ret) != n:
            raise EOFException()
        self._stats.count(ret)
        return ret

    def peek(self, n=1) -> str:
        with Peeker(self._fp):
            ret = self._fp.read(n)
        if len(ret) != n:
            raise EOFException()
        return ret

    def eof(self) -> bool:
        return self._fp.tell() >= self._size

    def skip(self, chars=" \t\n") -> str:
        read = ""
        while True:
            c = self._fp.read(1)
            if c == "":
                break
            if c not in chars:
                self._fp.seek(self._fp.tell() - 1, os.SEEK_SET)
                break
            read += c
        self._stats.count(read)
        return read

    def until(self, chars: str) -> str:
        read = ""
        while True:
            c = self._fp.read(1)
            if c == "":
                raise EOFException()
            if c in chars:
                self._fp.seek(self._fp.tell() - 1, os.SEEK_SET)
                break
            read += c
        self._stats.count(read)
        return read
    
    def until_loc(self, chars: str) -> Tuple[Location, str]:
        start = self.position()
        read = self.until(chars)
        end = self.position()
        return Location(self.filename, Range(start, end)), read

    def readr(self, pat: str | re.Pattern[str]) -> str:
        read = ""
        if isinstance(pat, str):
            pat = re.compile(pat)
        matched = False
        while True:
            c = self._fp.read(1)
            if c == "":
                raise EOFException()
            m = re.fullmatch(pat, read+c)
            if not matched and m is not None:
                matched = True
            elif matched and m is None:
                self._fp.seek(self._fp.tell() - 1, os.SEEK_SET)
                break
            read += c
        self._stats.count(read)
        return read

    def readr_loc(self, pat: str | re.Pattern[str]) -> Tuple[Location, str]:
        start = self.position()
        read = self.readr(pat)
        end = self.position()
        return Location(self.filename, Range(start, end)), read

    def through(self, chars: str) -> str:
        read = ""
        while True:
            c = self._fp.read(1)
            if c == "":
                raise EOFException()
            read += c
            if c in chars:
                break
        self._stats.count(read)
        return read
    
    def position(self) -> Position:
        return Position(self._stats.col, self._stats.line)

# Reader = FileReader | TextReader
Reader = FileReader
