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
  root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  load_dotenv(os.path.join(root_dir, ".env"))

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
      description="Audits store invoices/receipts, validates entries, GCS routes, JIRA support tickets for discrepancies, and generates a rich interactive expense breakdown pie chart, pivot table category bar charts, interactive price sliders with override warning banner, and clipboard copy CSV capabilities using A2UI.",
      tags=["invoice", "audit", "expense", "chart", "pivot", "csv", "override"],
      examples=[
          "Show my expense chart for this receipt",
          "Audit this invoice and show the expense breakdown",
          "Show the pivot table and download CSV",
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
      "display_name": "store_auditor_a2ui_v2",
      "description": (
          "An expert A2UI agent that audits store receipts and displays beautiful interactive expense charts."
      ),
      "agent_framework": "google-adk",
      "staging_bucket": storage,
      "gcs_dir_name": "store_auditor_a2ui_v2",
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
          os.path.join(root_dir, "agent.py"),
          os.path.join(root_dir, "executor.py"),
          os.path.join(root_dir, "tools.py"),
          os.path.join(root_dir, "components.py"),
          os.path.join(root_dir, "document_parser.py"),
          os.path.join(root_dir, "gemini_parser.py"),
          os.path.join(root_dir, "examples"),
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
  project_number = remote_engine_resource.split("/")[1]
  print(f"✓ Remote agent created. {remote_engine_resource}")

  a2a_endpoint = f"https://{api_endpoint}/v1beta1/{remote_engine_resource}/a2a/v1/card"
  bearer_token = _get_bearer_token()
  headers = {
      "Authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
  }

  print(f"✓ A2A endpoint: {a2a_endpoint}")

  response = httpx.get(a2a_endpoint, headers=headers, timeout=120.0)
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

  # Dynamically scan for a free authorization slot
  print("Scanning for free authorization slot on Gemini Enterprise...")
  bearer_token = _get_bearer_token()
  headers = {
      "Authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
      "X-Goog-User-Project": project_id
  }
  auths_url = f"https://global-discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/authorizations"
  auths_resp = requests.get(auths_url, headers=headers)
  auths_resp.raise_for_status()
  auth_slots_list = [auth["name"].split("/")[-1] for auth in auths_resp.json().get("authorizations", [] if auths_resp.json() else [])]
  
  combined_versions = []
  for slot in auth_slots_list:
      if slot.startswith("combined-auth-v"):
          try:
              ver = int(slot.split("-v")[-1])
              combined_versions.append(ver)
          except ValueError:
              pass
  
  max_ver = max(combined_versions) if combined_versions else 0
  next_ver = max_ver + 1
  target_slot = f"combined-auth-v{next_ver}"
  print(f"✓ Highest existing slot version found: v{max_ver}. Selected next slot: {target_slot}")
  
  print(f"Creating brand new authorization slot '{target_slot}'...")
  create_auth_url = f"https://global-discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/authorizations?authorizationId={target_slot}"
  client_id = os.environ.get("GOOGLE_CLIENT_ID")
  client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
  if not client_id or not client_secret:
      raise ValueError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variable in local .env configuration.")
  
  create_payload = {
      "name": f"projects/{project_id}/locations/global/authorizations/{target_slot}",
      "serverSideOauth2": {
          "clientId": client_id,
          "clientSecret": client_secret,
          "authorizationUri": f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
          "tokenUri": "https://oauth2.googleapis.com/token"
      }
  }
  
  create_resp = requests.post(create_auth_url, headers=headers, json=create_payload)
  if create_resp.status_code in (200, 201):
      print(f"✓ Authorization slot '{target_slot}' created successfully!")
  else:
      print(f"  - Note/Status when ensuring slot exists: {create_resp.status_code} - {create_resp.text}")

  registered_success = False
  auth_slots = [target_slot]
  for slot in auth_slots:
      if slot == "gamestop-auth-v17":
          print(f"Skipping slot '{slot}' to preserve the old version...")
          continue
      auth_uri = f"projects/{project_number}/locations/global/authorizations/{slot}"
      print(f"Attempting registration with slot '{slot}'...")
      try:
          enterprise_agent = _register_agent_on_gemini_enterprise(
              project_id=project_id,
              app_id=app_id,
              agent_card=a2ui_agent_card_str,
              agent_name="store_auditor_a2ui_v2",
              display_name="store_auditor_a2ui_v2",
              description="An expert A2UI agent that audits store receipts and displays beautiful interactive expense charts.",
              agent_authorization=auth_uri
          )
          print(f"✓ Agent registered successfully under slot: {slot}!")
          print(enterprise_agent)
          
          # Automatically clean up redundant agent cards to prevent workspace clutter
          active_agent_resource_name = enterprise_agent.get("name")
          _cleanup_redundant_agents(project_id, app_id, active_agent_resource_name)
          
          # Sync .env file
          env_file = os.path.join(root_dir, ".env")
          if os.path.exists(env_file):
              with open(env_file, "r") as f:
                  lines = f.readlines()
              with open(env_file, "w") as f:
                  for line in lines:
                      if line.startswith("AGENT_AUTHORIZATION="):
                          f.write(f"AGENT_AUTHORIZATION={auth_uri}\n")
                      else:
                          f.write(line)
              print(f"✓ Synced AGENT_AUTHORIZATION in .env to {slot}!")
          
          registered_success = True
          break
      except Exception as e:
          print(f"  - Slot '{slot}' failed or locked: {e}")

  if not registered_success:
      print("✗ Error: All pre-registered authorization slots are currently locked.")

  print("≈" * 120)

def _cleanup_redundant_agents(project_id: str, app_id: str, active_agent_resource_name: str):
    print("\nScanning for redundant Discovery Engine agent cards to delete...")
    api_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/collections/default_collection/engines/{app_id}/assistants/default_assistant/agents"
    bearer_token = _get_bearer_token()
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    try:
        resp = requests.get(api_endpoint, headers=headers)
        if resp.status_code != 200:
            print(f"  - Failed to list agents: {resp.status_code} - {resp.text}")
            return
        
        agents = resp.json().get("agents", [])
        active_agent_id = active_agent_resource_name.split("/")[-1]
        
        deleted_count = 0
        for agent in agents:
            name = agent["name"]
            agent_id = name.split("/")[-1]
            display_name = agent.get("displayName", "")
            
            # Check if it is a redundant store_auditor_a2ui agent
            if display_name in ("store_auditor_a2ui", "store_auditor_a2ui_v2") and agent_id != active_agent_id:
                print(f"  ⚠️ Redundant agent found: {agent_id} ({display_name}). Deleting...")
                delete_url = f"https://discoveryengine.googleapis.com/v1alpha/{name}"
                del_resp = requests.delete(delete_url, headers=headers)
                if del_resp.status_code in (200, 204):
                    print(f"  ✓ Successfully deleted redundant agent: {agent_id}")
                    deleted_count += 1
                else:
                    print(f"  ✗ Failed to delete agent {agent_id}: {del_resp.status_code} - {del_resp.text}")
        print(f"✓ Redundant agent cleanup complete. Deleted {deleted_count} stale agent cards.")
    except Exception as e:
        print(f"  - Exception during agent cleanup: {e}")


if __name__ == "__main__":
  main()
