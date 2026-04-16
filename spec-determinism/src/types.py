"""
spec-determinism: Data types shared across modules.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TypeKind(Enum):
    INT = "int"
    USIZE = "usize"
    ISIZE = "isize"
    U8 = "u8"
    U16 = "u16"
    U32 = "u32"
    U64 = "u64"
    I8 = "i8"
    I16 = "i16"
    I32 = "i32"
    I64 = "i64"
    BOOL = "bool"
    UNIT = "()"
    ENUM = "enum"
    STRUCT = "struct"
    SET = "Set"
    SEQ = "Seq"
    RESULT = "Result"
    OPTION = "Option"
    UNKNOWN = "unknown"


@dataclass
class TypeInfo:
    kind: TypeKind
    name: str                          # e.g. "Bitmap", "usize", "Result<usize, Error>"
    fields: list["FieldInfo"] = field(default_factory=list)      # for struct
    variants: list["VariantInfo"] = field(default_factory=list)  # for enum
    type_args: list["TypeInfo"] = field(default_factory=list)    # for generics
    spec_view: Optional["TypeInfo"] = None  # the type returned by @/@view


@dataclass
class FieldInfo:
    name: str
    type: TypeInfo


@dataclass
class VariantInfo:
    name: str
    inner: Optional[TypeInfo] = None


@dataclass
class Param:
    name: str
    type: TypeInfo
    is_mut_ref: bool = False   # &mut → split into pre/post
    is_ref: bool = False       # &    → input only
    is_self: bool = False      # self param


@dataclass
class FunctionSpec:
    name: str
    params: list[Param]
    return_type: TypeInfo
    requires: list[str]         # raw Verus clause strings
    ensures: list[str]          # raw Verus clause strings
    type_defs: dict[str, "TypeInfo"] = field(default_factory=dict)

    def input_vars(self) -> list[Param]:
        """All input variables (including pre-state of &mut params)."""
        return list(self.params)

    def output_vars(self) -> list[tuple[str, TypeInfo]]:
        """All output variables: (name, type) pairs.
        Names match gen_det parameter naming convention."""
        outs = []
        for p in self.params:
            if p.is_mut_ref:
                base = "self_" if p.is_self else p.name
                outs.append((f"post_{base}", p.type))
        outs.append(("result", self.return_type))
        return outs


@dataclass
class Assume:
    """A single narrowing constraint."""
    var_name: str
    expression: str       # Verus expression, e.g. "pre@.num_bits == 8"
    description: str = "" # human-readable


@dataclass
class VerifyResult:
    status: str           # "pass", "fail", "timeout", "error"
    function: str         # proof fn name
    duration_ms: int = 0
    stderr: str = ""


@dataclass
class ConcreteValue:
    """A fully concrete value for a variable."""
    var_name: str
    type_name: str
    fields: dict[str, str] = field(default_factory=dict)
    raw: str = ""              # if not a struct, just the value string


@dataclass
class Witness:
    """Complete witness with all fields concrete."""
    function: str
    inputs: dict[str, ConcreteValue] = field(default_factory=dict)
    output1: dict[str, ConcreteValue] = field(default_factory=dict)
    output2: dict[str, ConcreteValue] = field(default_factory=dict)
    assumes: list[Assume] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)  # [{round, phase, assumes, result}]
    gap_type: str = ""
    gap_description: str = ""
