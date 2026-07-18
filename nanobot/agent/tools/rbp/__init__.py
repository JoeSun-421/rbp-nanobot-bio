# -*- coding: utf-8 -*-
"""
Proposal §6.2 — nanobot/agent/tools/rbp/

P0–P2 tools as nanobot.agent.tools.base.Tool subclasses.
When this package is installed into the real nanobot tree
(``agent/tools/rbp/``), ToolLoader can discover classes with
``_plugin_discoverable = True``.
"""

from nanobot.agent.tools.rbp.annotation import GetFuncAnnotationTool, LiteratureSearchTool
from nanobot.agent.tools.rbp.catalogue import GetKnownRBPListTool
from nanobot.agent.tools.rbp.predict import PredictInteractionTool
from nanobot.agent.tools.rbp.seq import SeqSimilarityTool
from nanobot.agent.tools.rbp.structure import PredictStructureTool, StructSimilarityTool

# Explicit list for register_all()
ALL_RBP_TOOL_CLASSES = [
    PredictInteractionTool,
    GetKnownRBPListTool,
    SeqSimilarityTool,
    StructSimilarityTool,
    GetFuncAnnotationTool,
    PredictStructureTool,
    LiteratureSearchTool,
]

__all__ = [
    "ALL_RBP_TOOL_CLASSES",
    "PredictInteractionTool",
    "GetKnownRBPListTool",
    "SeqSimilarityTool",
    "StructSimilarityTool",
    "GetFuncAnnotationTool",
    "PredictStructureTool",
    "LiteratureSearchTool",
    "register_all",
]


def register_all(registry) -> list[str]:
    """Instantiate and register all proposal RBP tools on a ToolRegistry."""
    names = []
    for cls in ALL_RBP_TOOL_CLASSES:
        tool = cls()
        registry.register(tool)
        names.append(tool.name)
    return names
