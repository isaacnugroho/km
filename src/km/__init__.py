"""Knowledge Management MCP."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("km")
except PackageNotFoundError:
    __version__ = "0.5.1"
