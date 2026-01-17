#
# Gramps Plugin Registration File
#
# This file registers the Smart Search tool with Gramps
#

register(
    TOOL,
    id="smart_search",
    name=_("Smart Search Router"),
    description=_("AI-powered search routing for genealogical databases"),
    version="0.1.0",
    gramps_target_version="5.2",
    status=STABLE,
    fname="smart_search.py",
    authors=["Thomas Vincent"],
    authors_email=[""],
    category=TOOL_UTILS,
    toolclass="SmartSearchTool",
    optionclass="SmartSearchOptions",
    tool_modes=[TOOL_MODE_GUI],
)
