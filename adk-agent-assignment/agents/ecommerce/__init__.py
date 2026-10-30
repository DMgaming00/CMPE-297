"""ADK agent package.

``agent`` is imported lazily so that helper subprocesses (e.g. the local MCP server)
can import sibling modules without constructing the ADK agent.  ``adk web`` imports
``<package>.agent`` directly and ``adk eval`` accesses ``<package>.agent``.
"""

from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    if name == "agent":
        return import_module(f"{__name__}.agent")
    raise AttributeError(name)
