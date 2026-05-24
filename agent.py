import os
import logging
from google.adk.agents import Agent
from google.adk.tools import FunctionTool, load_artifacts
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import VERSION_0_8

logger = logging.getLogger(__name__)

# Sibling relative-absolute fallback imports for tools
try:
    from .tools import (
        extract_data_tool,
        validate_data_tool,
        route_document_tool,
        create_jira_ticket_tool,
        analyze_uploaded_invoice_tool,
        audit_invoice_tool
    )
except ImportError:
    from tools import (
        extract_data_tool,
        validate_data_tool,
        route_document_tool,
        create_jira_ticket_tool,
        analyze_uploaded_invoice_tool,
        audit_invoice_tool
    )


ROLE_DESCRIPTION = "You are the lead store invoice auditor coordinating a multi-agent pipeline. Your job is to audit retail store receipts, coordinate specialists, and generate beautiful interactive visual expense pie charts."

WORKFLOW_DESCRIPTION = """
For Invoice Auditing & Expense Chart Queries:
1. When the user uploads or refers to an invoice/receipt file in the session context, you MUST call the `analyze_uploaded_invoice_tool` to trigger the specialized multi-agent pipeline in-memory.
2. Explain each step of the pipeline (Extraction, Audit validation, GCS routing, and JIRA support ticketing if applicable) in your final response.
3. Parse the returned JSON from your tool, extracting the merchant name, subtotal, line items, tax, GCS bucket path, and JIRA ticket status.
4. Generate a clean interactive VegaChart (using mark "arc" for a pie chart or donut chart) representing the visual expense breakdown of the final total (mapping each line item and the tax to a slice of the pie).
5. Present the structured results and audit summary along with the pie chart.
"""

UI_DESCRIPTION = """
- For invoice expense charts, you MUST generate an interactive pie/donut chart using the VegaChart component with `"mark": {"type": "arc", "outerRadius": 100, "tooltip": true}`. Set `"theta": {"field": "value", "type": "quantitative"}` and `"color": {"field": "category", "type": "nominal"}` in the encodings to represent each expense segment (line items and tax).
- The chart or dashboard data MUST be wrapped in `<a2ui-json>` and `</a2ui-json>` tags. DO NOT output raw JSON without these tags.
"""


# --- Specialist Agent Definitions ---

# 1. JIRA Support Specialist Agent
jira_agent = Agent(
    name="jira_agent",
    model=os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
    description="Expert JIRA support assistant sub-agent.",
    instruction="""You are an expert JIRA support assistant. Your sole task is to use your create_jira_ticket_tool to automatically create support tickets in JIRA when requested.""",
    tools=[FunctionTool(create_jira_ticket_tool)]
)

# 2. Specialist Data Extractor Agent
data_extractor_agent = Agent(
    name="data_extractor",
    model=os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
    description="Expert retail document parser sub-agent.",
    instruction="""You are an expert retail document parser. Use the extract_data_tool to parse receipt or invoice documents, identifying store name, date, tax, total, and detailed line items.""",
    tools=[FunctionTool(extract_data_tool)]
)

# 3. Specialist Validation Agent
validator_agent = Agent(
    name="validator",
    model=os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
    description="Retail receipt validation auditor sub-agent.",
    instruction="""You are a retail receipt validation auditor. Use the validate_data_tool to audit extracted invoice text directly against what is visually readable from the receipt.""",
    tools=[FunctionTool(validate_data_tool)]
)

# 4. Specialist Scoring and Routing Agent
scoring_routing_agent = Agent(
    name="scoring_router",
    model=os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
    description="Retail scoring and GCS routing sub-agent.",
    instruction="""You are a retail scoring and document routing agent. Use the route_document_tool to archive receipts to the correct GCS bucket. If the validation score is below 3, delegate to your sub-agent jira_agent.""",
    tools=[FunctionTool(route_document_tool)],
    sub_agents=[jira_agent]
)


def create_agent() -> Agent:
    schema_manager = A2uiSchemaManager(
        version=VERSION_0_8,
        catalogs=[
            BasicCatalog.get_config(
                version=VERSION_0_8,
                examples_path=os.path.join(
                    os.path.dirname(__file__), "examples/0.8"
                ),
            )
        ],
        schema_modifiers=[remove_strict_validation],
    )

    instruction = schema_manager.generate_system_prompt(
        role_description=ROLE_DESCRIPTION,
        workflow_description=WORKFLOW_DESCRIPTION,
        ui_description=UI_DESCRIPTION,
        include_schema=True,
        include_examples=True,
        validate_examples=False,
    )

    # Lead Orchestrator Agent (Root Agent)
    orchestrator_agent = Agent(
        name="StoreInvoiceAuditorAgent",
        model=os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
        description="Lead Store Auditor orchestrating OCR, visual audit, routing, and A2UI charting.",
        instruction=instruction,
        tools=[load_artifacts, FunctionTool(analyze_uploaded_invoice_tool), audit_invoice_tool],
        sub_agents=[data_extractor_agent, validator_agent, scoring_routing_agent]
    )

    return orchestrator_agent


_root_agent = None

def get_agent() -> Agent:
    global _root_agent
    if _root_agent is None:
        _root_agent = create_agent()
    return _root_agent

root_agent = get_agent()
