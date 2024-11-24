from typing import Optional, Any, List
from dataclasses import dataclass, field
import abc
from .location import Location


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
    A bare identifer, like 'i64'
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
class FunctionName(Name):
    """
    @-prefixed names, also used for constants
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
class Function(IR):
    name: FunctionName
    # formals: List[Formal]
    # attribute: Optional[AttributeName]


@dataclass
class Define(Function):
    statements: List[Statement | Label]


@dataclass
class Declare(Function):
    pass


@dataclass
class Constant(IR):
    name: FunctionName


@dataclass
class Metadata(IR):
    name: MetadataName


@dataclass
class Attribute(IR):
    name: AttributeName


@dataclass
class Module(IR):
    source_filename: SourceFilename
    target_info: List[TargetString]
    types: List[TypeDefinition]
    constants: List[Constant]
    functions: List[Function]
    metadata: List[Metadata]
