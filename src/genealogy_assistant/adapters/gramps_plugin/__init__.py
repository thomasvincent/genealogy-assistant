"""Gramps Desktop Plugin Adapter.

This module provides a Gramps plugin for the Smart Search Router.

Installation:
1. Copy this directory to ~/.gramps/gramps51/plugins/
2. Restart Gramps
3. Access via Tools > Smart Search

Or symlink for development:
ln -s /path/to/genealogy-assistant/src/genealogy_assistant/adapters/gramps_plugin ~/.gramps/gramps51/plugins/smart_search
"""

from genealogy_assistant.adapters.gramps_plugin.smart_search import SmartSearchTool

__all__ = ["SmartSearchTool"]
