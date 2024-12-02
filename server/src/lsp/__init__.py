import lsprotocol.types as lsT
from pygls.server import LanguageServer
from dataclasses import dataclass, field
import lllsp.ir.location as location
from lllsp.parser import IRParser, NameParser
from lllsp.parser.reader import Reader
from typing import List, Dict, Iterable, Tuple, Optional
import lllsp.ir as ir
import sys
from lllsp.segments import PositionList
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

def range_to_lines(rng: location.Range, lines: List[str]) -> List[str]:
    if rng.start.line == rng.end.line:
        return [lines[rng.start.line][rng.start.column:rng.end.column]]
    
    res = [
        lines[rng.start.line][rng.start.column:]
    ]
    for idx in range(rng.start.line+1, rng.end.line):
        res.append(lines[idx])
    res.append(lines[rng.end.line][:rng.end.column])
    return res

def range_to_text(rng: location.Range, lines: List[str]) -> str:
    return "\n".join(range_to_lines(rng, lines))

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
    
    @property
    def filename(self):
        return self.uri.removeprefix("file://")

    # @functools.lru_cache(maxsize=None)
    def _lines(self):
        with open(self.filename, "r") as f:
            return f.readlines()

    def lines(self, rng: Optional[location.Range]) -> List[str]:
        lines = self._lines()
        if rng:
            return range_to_lines(rng, lines)
        return lines

        


class LLLSP(LanguageServer):
    def __init__(self):
        super().__init__("lllsp", "v0.1")

        self.files: Dict[str, FileInfo] = dict()

    def file_info(self, uri: str, rebuild=False) -> FileInfo:

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
        # TODO: instead of using the uri, can I avoid file IO overhead by parsing the string? does it matter that much?
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

    @server.feature(lsT.TEXT_DOCUMENT_HOVER)
    async def hover(ls: LLLSP, params: lsT.HoverParams):
        text_doc = ls.workspace.get_text_document(params.text_document.uri)
        fi = ls.file_info(text_doc.uri)

        pos = params.position


        log("hover")
        if seg := fi.find_name_segment(pos):
            log("seg", seg)
            if i := fi.resolve(seg):
                log("i", i)
                loc = i.location
                log(loc.rng)
                # get the first line of the location
                line = fi.lines(loc.rng)[0].strip()
                content = lsT.MarkedString_Type1("llvm", line)
                hov = lsT.Hover(content, rng_to_lsprng(loc.rng))
                return hov
        return None

    @server.feature(lsT.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    async def doc_sym(ls: LLLSP, params: lsT.DocumentSymbolParams):
        text_doc = ls.workspace.get_text_document(params.text_document.uri)
        fi = ls.file_info(text_doc.uri)

        si = []
        # TODO: actually implement this
        for i in fi.functions():
            s = lsT.SymbolInformation(loc_to_lsploc(i.location), i.name.basename(), lsT.SymbolKind.Function)
            si.append(s)
        return si

    server.start_io()

