from typing import Optional, Any, List, Sequence
from dataclasses import dataclass, field
import abc
from .location import Location
import itertools


@dataclass
class IR:
    location: Location

@dataclass
class SourceFilename(IR):
    filename: str


@dataclass
class TargetString(IR):
    kind: str
    value: str


@dataclass
class Name(IR, metaclass=abc.ABCMeta):
    name: str

    @abc.abstractmethod
    def basename(self) -> str:
        pass


@dataclass
class BareName(Name):
    """
    A bare identifier, like 'i64'
    """

    def basename(self) -> str:
        return self.name


@dataclass
class ValueName(Name):
    """
    %-prefixed names, also used for types
    """

    def basename(self) -> str:
        return self.name.removeprefix("%")


@dataclass
class SymbolName(Name):
    """
    @-prefixed names, used for functions and constants
    """

    def basename(self) -> str:
        return self.name.removeprefix("@")



@dataclass
class MetadataName(Name):
    """
    !-prefixed names
    """

    def basename(self) -> str:
        return self.name.removeprefix("!")



@dataclass
class AttributeName(Name):
    """
    #-prefixed names
    """

    def basename(self) -> str:
        return self.name.removeprefix("#")


@dataclass
class Label(Name):
    """
    :-suffixed names
    """
    
    def basename(self) -> str:
        return self.name.removesuffix(":")



@dataclass
class TypeDefinition(IR):
    name: ValueName


@dataclass
class Formal(IR):
    name: ValueName
    type_: BareName


@dataclass
class Statement(IR, metaclass=abc.ABCMeta):
    pass


@dataclass
class VoidStatement(Statement):
    pass


@dataclass
class StatementWithValue(Statement):
    value: ValueName


@dataclass
class Function(IR, metaclass=abc.ABCMeta):
    name: SymbolName
    # formals: List[Formal]
    # attribute: Optional[AttributeName]
    
    def add(self, i: IR):
        raise ValueError("don't know how to add that")

    def resolve(self, i: Name):
        return None

@dataclass
class Define(Function):
    statements: List[Statement | Label]

    def add(self, i: IR):
        if isinstance(i, (Statement, Label)):
            self.statements.append(i)
        else:
            super().add(i)
    
    def resolve(self, i: Name):
        if x := super().resolve(i):
            return x
    
        for s in self.statements:
            if isinstance(s, Label) and s.name.removesuffix(":") == i.name.removeprefix("%"):
                return s
            elif isinstance(s, StatementWithValue) and s.value.name == i.name:
                return s
        return None


@dataclass
class Declare(Function):
    pass


@dataclass
class Constant(IR):
    name: SymbolName


@dataclass
class Metadata(IR):
    name: MetadataName


@dataclass
class Attribute(IR):
    name: AttributeName


@dataclass
class Module(IR):
    source_filename: Optional[SourceFilename] = field(default=None)
    target_info: List[TargetString] = field(default_factory=list)
    types: List[TypeDefinition] = field(default_factory=list)
    constants: List[Constant] = field(default_factory=list)
    functions: List[Function] = field(default_factory=list)
    metadata: List[Metadata] = field(default_factory=list)


    def add(self, i: IR):
        if isinstance(i, SourceFilename):
            self.source_filename = i
        elif isinstance(i, TargetString):
            self.target_info.append(i)
        elif isinstance(i, TypeDefinition):
            self.types.append(i)
        elif isinstance(i, Constant):
            self.constants.append(i)
        elif isinstance(i, Function):
            self.functions.append(i)
        elif isinstance(i, Metadata):
            self.metadata.append(i)
        else:
            raise ValueError("don't know how to add that")

    def resolve(self, i: Name) -> Optional[IR]:
        """
        Return the IR element this name refers to
        """
        if isinstance(i, ValueName):
            # it could be a typedef or a statement in a function
            for f in self.functions:
                if i.location.rng in f.location.rng:
                    if res := f.resolve(i):
                        return res
                    
            # if we get here, its a typedef
            for t in self.types:
                if i.name == t.name.name:
                    return t
        elif isinstance(i, SymbolName):
            # it could be a constant or function
            for c in itertools.chain(self.functions, self.constants):
                if i.name == c.name.name:
                    return c
        elif isinstance(i, Metadata):
            for m in self.metadata:
                if i.name == m.name.name:
                    return m
                
        return None

