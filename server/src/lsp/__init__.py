import lsprotocol.types as lsT
from pygls.server import LanguageServer
from dataclasses import dataclass, field
import ir.location as location
from parser import IRParser, NameParser
from parser.reader import Reader
from typing import List, Dict, Iterable, Tuple, Optional
import ir
import sys
from segments import PositionList
import functools

def log(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)

def pos_to_lsppos(pos: location.Position):
    return lsT.Position(pos.line, pos.column)

def rng_to_lsprng(rng: location.Range):
    return lsT.Range(pos_to_lsppos(rng.start), pos_to_lsppos(rng.end))

def loc_to_lsploc(loc: location.Location):
    return lsT.Location(loc.filename, rng_to_lsprng(loc.rng))

def lsppos_to_pos(pos: lsT.Position):
    return location.Position(pos.character, pos.line)

def lsprng_to_rng(rng: lsT.Range):
    return location.Range(lsppos_to_pos(rng.start), lsppos_to_pos(rng.end))

def lsploc_to_loc(loc: lsT.Location):
    return location.Location(loc.uri, lsprng_to_rng(loc.range))

@dataclass
class LSPIRName:
    """
    A wrapper class around ir.Name, with lsp helpers
    """
    name: ir.Name
    
    @functools.cached_property
    def rng(self):
        return rng_to_lsprng(self.name.location.rng)

@dataclass
class FileInfo:
    uri: str
    module: ir.Module
    name_segments: PositionList[LSPIRName] = field(init=False)

    def __post_init__(self):
        self.name_segments = PositionList(lambda x: x.rng)

    def build_name_segments(self, names: List[ir.Name]):
        self.name_segments.clear()
        for n in names:
            self.name_segments.append(LSPIRName(n))
        self.name_segments.sort()

    def functions(self) -> Iterable[ir.Function]:
        yield from self.module.functions
    
    def find_name_segment(self, pos: lsT.Position) -> Optional[LSPIRName]:
        """
        find the segment at the location, or None
        """
        return self.name_segments.find(pos)
    
    def resolve(self, n: LSPIRName) -> Optional[ir.IR]:
        """
        resolve a name to its definition, if any
        """
        return self.module.resolve(n.name)
        


class LLLSP(LanguageServer):
    def __init__(self):
        super().__init__("lllsp", "v0.1")

        self.files: Dict[str, FileInfo] = dict()

    def file_info(self, uri: str, rebuild=False):

        if rebuild or uri not in self.files:
            filename = uri.removeprefix("file://")
            log(f"parsing {uri}")
            with Reader(filename) as r:
                parser = IRParser()
                f = FileInfo(uri, parser.parse(r))
            log(f"finished ir parsing {uri}")
            with Reader(filename) as r:
                parser = NameParser()
                f.build_name_segments(parser.parse(r))
            log(f"finished parsing {uri}")
            self.files[uri] = f
            return f
        else:
            return self.files[uri]


def run_lsp():

    server = LLLSP()

    @server.feature(lsT.TEXT_DOCUMENT_DID_OPEN)
    async def did_open(ls: LLLSP, params: lsT.DidOpenTextDocumentParams):
        uri = params.text_document.uri
        fi = ls.file_info(uri)


    @server.feature(lsT.TEXT_DOCUMENT_DID_SAVE)
    async def did_save(ls: LLLSP, params: lsT.DidSaveTextDocumentParams):
        uri = params.text_document.uri
        fi = ls.file_info(uri, rebuild=True)


    @server.feature(lsT.TEXT_DOCUMENT_DECLARATION)
    @server.feature(lsT.TEXT_DOCUMENT_DEFINITION)
    async def goto_def(ls: LLLSP, params: lsT.DeclarationParams | lsT.DefinitionParams):
        uri = params.text_document.uri
        fi = ls.file_info(uri)

        pos = params.position

        locs = []
        # find the symbol and goto
        log("gotodef")
        if seg := fi.find_name_segment(pos):
            log("seg", seg)
            if i := fi.resolve(seg):
                log("i", i)
                loc = i.location
                if isinstance(i, (ir.Function, ir.TypeDefinition, ir.Metadata, ir.Constant, ir.Attribute)):
                    loc = i.name.location
                elif isinstance(i,  ir.StatementWithValue):
                    loc = i.value.location
                locs.append(loc_to_lsploc(loc))
        return locs

    @server.feature(lsT.TEXT_DOCUMENT_REFERENCES)
    async def refs(ls: LLLSP, params: lsT.ReferenceParams):
        uri = params.text_document.uri
        fi = ls.file_info(uri)

        pos = params.position

        locs = []
        log("refs")
        if seg := fi.find_name_segment(pos):
            log("seg", seg)
            if i := fi.resolve(seg):
                log("i", i)
                loc = i.location
                if isinstance(i, ir.Function):
                    loc = i.name.location
                locs.append(loc_to_lsploc(loc))
            # TODO add a module.references()
        return locs

    @server.feature(lsT.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    async def doc_sym(ls: LLLSP, params: lsT.DocumentSymbolParams):
        text_doc = ls.workspace.get_text_document(params.text_document.uri)
        fi = ls.file_info(text_doc.uri)

        si = []
        for i in fi.functions():
            s = lsT.SymbolInformation(loc_to_lsploc(i.location), i.name.basename(), lsT.SymbolKind.Function)
            si.append(s)
        return si

    server.start_io()

