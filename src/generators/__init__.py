# This is the init file for the generators
from .dotnet import CSharpGenerator
from .go import GoGenerator
from .python import PythonGenerator
from .typescript import TypeScriptGenerator
from .proto import ProtoGenerator

__all__ = [
    "CSharpGenerator",
    "GoGenerator",
    "PythonGenerator",
    "TypeScriptGenerator",
    "ProtoGenerator",
]
