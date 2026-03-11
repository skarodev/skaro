"""Smart context module — tiered project context for LLM prompts.

Provides AST-based signature extraction (tree-sitter), relevance-based
file selection, and a unified builder that produces compact, informative
context at a fraction of the token cost of sending all source files.
"""

from skaro_core.context._ast_index import build_project_index, extract_signatures
from skaro_core.context._relevance import find_relevant_paths
from skaro_core.context._smart_context import SmartContext, SmartContextBuilder

__all__ = [
    "SmartContext",
    "SmartContextBuilder",
    "build_project_index",
    "extract_signatures",
    "find_relevant_paths",
]
