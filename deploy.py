"""Deployment script for the Combined Agent."""

import json
import os

from a2a.types import AgentSkill
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport.requests import Request
from google.genai import types
import httpx
import requests
import vertexai
from vertexai.preview.reasoning_engines import A2aAgent
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card

# Import the StoreAuditorExecutor
from executor import StoreAuditorExecutor


def _get_bearer_token():
  """Gets a bearer token for authenticating with Google Cloud."""
  try:
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    request = Request()
    credentials.refresh(request)
    return credentials.token
  except Exception as e:  # pylint: disable=broad-except
    print(f"Error getting credentials: {e}")
    print(
        "Please ensure you have authenticated with 'gcloud auth "
        "application-default login'."
    )
  return None


def _register_agent_on_gemini_enterprise(
    project_id: str,
    app_id: str,
    agent_card: str,
    agent_name: str,
    display_name: str,
    description: str,
    agent_authorization: str | None = None,
):
  """Register an Agent Engine to Gemini Enterprise."""
  api_endpoint = (
      f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/"
      f"locations/global/collections/default_collection/engines/{app_id}/"
      "assistants/default_assistant/agents"
  )

  payload = {
      "name": agent_name,
      "displayName": display_name,
      "description": description,
      "a2aAgentDefinition": {"jsonAgentCard": agent_card},
  }

  if agent_authorization:
    payload["authorization_config"] = {"agent_authorization": agent_authorization}

  bearer_token = _get_bearer_token()
  headers = {
      "Authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
      "X-Goog-User-Project": project_id,
  }

  response = requests.post(api_endpoint, headers=headers, json=payload)

  if response.status_code == 200:
    print("✓ Agent registered successfully!")
    return response.json()
  print(f"✗ Registration failed with status code: {response.status_code}")
  print(f"Response: {response.text}")
  response.raise_for_status()


def main():
  load_dotenv()

  project_id = os.environ.get("PROJECT_ID")
  location = os.environ.get("LOCATION")
  storage = os.environ.get("STORAGE_BUCKET")
  app_id = os.environ.get("GEMINI_ENTERPRISE_APP_ID")
  api_endpoint = f"{location}-aiplatform.googleapis.com"

  print("≈" * 120)

  vertexai.init(
      project=project_id,
      location=location,
      api_endpoint=api_endpoint,
      staging_bucket=storage,
  )

  print("✓ Vertex AI client initialized.")

  client = vertexai.Client(
      project=project_id,
      location=location,
      http_options=types.HttpOptions(
          api_version="v1beta1",
      ),
  )
  print("✓ Vertex AI client created.")

  # Define skills
  skill_auditor = AgentSkill(
      id="store-invoice-auditor-chart",
      name="Store Invoice Auditor & Expense Chart",
      description="Audits store invoices/receipts, validates entries, GCS routes, JIRA support tickets for discrepancies, and generates a rich interactive expense breakdown pie chart using A2UI.",
      tags=["invoice", "audit", "expense", "chart"],
      examples=[
          "Show my expense chart for this receipt",
          "Audit this invoice and show the expense breakdown",
      ],
  )

  store_auditor_agent_card = create_agent_card(
      agent_name="Store Invoice Auditor",
      description="Expert retail auditor that analyzes invoices and displays beautiful interactive expense charts.",
      skills=[skill_auditor],
      default_input_modes=["text/plain"],
      default_output_modes=["text/plain"],
  )

  print(f"✓ Store Auditor agent card created. {store_auditor_agent_card}")

  # Create A2aAgent with StoreAuditorExecutor
  a2ui_agent = A2aAgent(
      agent_card=store_auditor_agent_card,
      agent_executor_builder=StoreAuditorExecutor,
  )
  a2ui_agent.set_up()

  print("✓ Local Auditor agent created.")

  config = {
      "display_name": "store_auditor_a2ui",
      "description": (
          "An expert A2UI agent that audits store receipts and displays beautiful interactive expense charts."
      ),
      "agent_framework": "google-adk",
      "staging_bucket": storage,
      "gcs_dir_name": "store_auditor_a2ui",
      "requirements": [
          "google-cloud-aiplatform[agent_engines,adk]==1.148.0",
          "google-genai==1.73.1",
          "python-dotenv==1.2.2",
          "uvicorn==0.44.0",
          "a2a-sdk==0.3.26",
          "cloudpickle==3.1.2",
          "pydantic==2.13.1",
          "jsonschema==4.26.0",
          "a2ui-agent-sdk==0.2.1",
          "fastapi==0.136.0",
          "atlassian-python-api",
          "Pillow",
          "google-cloud-storage",
      ],
      "http_options": {
          "api_version": "v1beta1",
      },
      "max_instances": 1,
      "extra_packages": [
          "agent.py",
          "executor.py",
          "tools.py",
          "document_parser.py",
          "gemini_parser.py",
          "examples",
      ],
      "env_vars": {
          "NUM_WORKERS": "1",
          "GOOGLE_GENAI_USE_VERTEXAI": "true",
          "PROJECT_ID": project_id,
          "LOCATION": location,
          "GOOGLE_CLOUD_LOCATION": location,
          "NESS_PROCESSED_DOCS_BUCKET": os.environ.get("NESS_PROCESSED_DOCS_BUCKET"),
          "NESS_HUMAN_REVIEW_BUCKET": os.environ.get("NESS_HUMAN_REVIEW_BUCKET"),
          "JIRA_EMAIL": os.environ.get("JIRA_EMAIL"),
          "JIRA_API_TOKEN": os.environ.get("JIRA_API_TOKEN"),
      },
  }

  remote_agent = client.agent_engines.create(agent=a2ui_agent, config=config)

  remote_engine_resource = remote_agent.api_resource.name
  print(f"✓ Remote agent created. {remote_engine_resource}")

  a2a_endpoint = f"https://{api_endpoint}/v1beta1/{remote_engine_resource}/a2a/v1/card"
  bearer_token = _get_bearer_token()
  headers = {
      "Authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
  }

  print(f"✓ A2A endpoint: {a2a_endpoint}")

  response = httpx.get(a2a_endpoint, headers=headers)
  response.raise_for_status()
  a2ui_agent_card_json = response.json()
  
  # Add A2UI capabilities to the agent card.
  a2ui_agent_card_json["capabilities"] = {
      "streaming": False,
      "extensions": [{
          "uri": "https://a2ui.org/a2a-extension/a2ui/v0.8",
          "description": "Ability to render A2UI",
          "required": False,
          "params": {
              "supportedCatalogIds": [
                  "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
              ]
          },
      }],
  }
  a2ui_agent_card_str = json.dumps(a2ui_agent_card_json)

  print("✓ A2UI agent card fetched.")

  enterprise_agent = _register_agent_on_gemini_enterprise(
      project_id=project_id,
      app_id=app_id,
      agent_card=a2ui_agent_card_str,
      agent_name="store_auditor_a2ui",
      display_name="store_auditor_a2ui",
      description="An expert A2UI agent that audits receipts and displays interactive expense charts.",
      agent_authorization=os.environ.get("AGENT_AUTHORIZATION"),
  )

  print(enterprise_agent)
  print("≈" * 120)


if __name__ == "__main__":
  main()
