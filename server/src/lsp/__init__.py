from lsprotocol.types import *
from pygls.server import LanguageServer
from dataclasses import dataclass
import ir.location as location
from parser import IRParser
from parser.reader import Reader
from typing import List, Dict
import ir
import sys

def log(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)

def pos_to_lsppos(pos: location.Position):
    return Position(pos.line, pos.column)

def rng_to_lsprng(rng: location.Range):
    return Range(pos_to_lsppos(rng.start), pos_to_lsppos(rng.end))

def loc_to_lsploc(loc: location.Location):
    return Location(loc.filename, rng_to_lsprng(loc.rng))

@dataclass
class FileInfo:
    uri: str
    ir: List[ir.IR]


class LLLSP(LanguageServer):
    def __init__(self):
        super().__init__("lllsp", "v0.1")

        self.files: Dict[str, FileInfo] = dict()

    def file_info(self, uri: str, rebuild=False):

        if rebuild or uri not in self.files:
            parser = IRParser()
            filename = uri.removeprefix("file://")
            with Reader(filename) as r:
                f = FileInfo(uri, parser.parse(r))
            self.files[uri] = f
            return f
        else:
            return self.files[uri]


def run_lsp():

    server = LLLSP()

    @server.feature(TEXT_DOCUMENT_DID_OPEN)
    async def did_open(ls: LLLSP, params: DidOpenTextDocumentParams):
        uri = params.text_document.uri
        fi = ls.file_info(uri)


    @server.feature(TEXT_DOCUMENT_DID_SAVE)
    async def did_save(ls: LLLSP, params: DidSaveTextDocumentParams):
        uri = params.text_document.uri
        fi = ls.file_info(uri, rebuild=True)


    @server.feature(TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    async def get_sym(ls: LLLSP, params: DocumentSymbolParams):
        text_doc = ls.workspace.get_text_document(params.text_document.uri)
        fi = ls.file_info(text_doc.uri)

        si = []
        for i in fi.ir:
            if isinstance(i, ir.Define):
                s = SymbolInformation(loc_to_lsploc(i.location), i.name.basename(), SymbolKind.Function)
                si.append(s)
        return si

    server.start_io()

