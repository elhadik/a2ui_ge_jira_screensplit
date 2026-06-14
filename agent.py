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
        audit_invoice_tool,
        generate_audit_a2ui_dashboard_tool
    )
except ImportError:
    from tools import (
        extract_data_tool,
        validate_data_tool,
        route_document_tool,
        create_jira_ticket_tool,
        analyze_uploaded_invoice_tool,
        audit_invoice_tool,
        generate_audit_a2ui_dashboard_tool
    )



ROLE_DESCRIPTION = "You are the lead store invoice auditor coordinating a multi-agent retail operations pipeline. Your job is to audit retail store receipts, coordinate specialists, and present a premium interactive visual audit dashboard and override workflow on the right-hand side panel."

WORKFLOW_DESCRIPTION = """
For Invoice Auditing & Expense Queries:
1. When the user uploads or refers to a receipt/invoice file in the session context, you MUST call the `analyze_uploaded_invoice_tool` (or `audit_invoice_tool`) to trigger the OCR, Gemini visual auditing, routing, and A2UI generation pipeline.
2. The tool automatically returns both the JSON analysis payload AND the pre-compiled `<a2ui-json>` dashboard XML block at the bottom of its output.
3. You MUST print the returned `<a2ui-json>` XML block exactly as-is at the end of your response to render the premium side-panel dashboard. Do NOT modify, truncate, or rewrite any characters in the XML block!
4. In your text summary, explain the audit steps taken:
   - **OCR Extraction**: Store name, date, items extraction.
   - **Gemini Visual Audit Validation**: Discrepancies assessment and confidence score.
   - **GCS Archiving**: Routed bucket (processed vs review).
   - **JIRA Ticketing Status**: Automated manual-review ticket generation.
5. For Manual Discrepancy Override Trigger prompts (e.g., when the user prompts "File a JIRA manual review ticket due to audited discrepancies." triggered by A2UI action button clicks):
   - Call `create_jira_ticket_tool` with a concise title (e.g., "AUDITOR OVERRIDE: Discrepancies found in store invoice") and a detailed description of the overridden values.
   - Confirm to the user that the review ticket has been logged and manual override is active.
"""

UI_DESCRIPTION = """
- You MUST copy and print the `<a2ui-json>` block returned by your tools exactly as-is. This renders the premium, dark-themed visual dashboard containing KPIs, line items table, reactive price sliders, dynamic override warning banner, and live Chart.js expense bar charts on the side-panel.
- The dashboard surface also renders native action buttons right below it:
  1. `"btn_approve"` ("✅ Approve & Archive"): Triggers user prompt validating extraction.
  2. `"btn_manual_jira"` ("🚨 File JIRA Ticket"): Triggers user prompt to file a JIRA manual review ticket.
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
                ) if os.path.exists(os.path.join(os.path.dirname(__file__), "examples/0.8")) else None,
            )
        ],
        schema_modifiers=[remove_strict_validation],
    )

    instruction = schema_manager.generate_system_prompt(
        role_description=ROLE_DESCRIPTION,
        workflow_description=WORKFLOW_DESCRIPTION,
        ui_description=UI_DESCRIPTION,
        include_schema=False,
        include_examples=False,
        validate_examples=False,
    )

    # Lead Orchestrator Agent (Root Agent)
    orchestrator_agent = Agent(
        name="StoreInvoiceAuditorAgent",
        model=os.environ.get("GOOGLE_GENAI_MODEL", "gemini-2.5-flash"),
        description="Lead Store Auditor orchestrating OCR, visual audit, routing, and premium dashboard visual override controls.",
        instruction=instruction,
        tools=[
            load_artifacts, 
            FunctionTool(analyze_uploaded_invoice_tool), 
            FunctionTool(create_jira_ticket_tool),
            audit_invoice_tool
        ],
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
