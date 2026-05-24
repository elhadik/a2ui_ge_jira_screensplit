import os
import json
import requests
import httpx
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport.requests import Request

def _get_bearer_token():
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    return credentials.token

def main():
    load_dotenv()
    project_id = os.environ.get("PROJECT_ID")
    app_id = os.environ.get("GEMINI_ENTERPRISE_APP_ID")
    location = os.environ.get("LOCATION")
    
    remote_engine = "projects/943928157761/locations/us-central1/reasoningEngines/6242537190081953792"
    a2a_endpoint = f"https://{location}-aiplatform.googleapis.com/v1beta1/{remote_engine}/a2a/v1/card"
    
    headers = {"Authorization": f"Bearer {_get_bearer_token()}", "Content-Type": "application/json"}
    
    print("Fetching A2UI agent card from reasoning engine...")
    response = httpx.get(a2a_endpoint, headers=headers)
    response.raise_for_status()
    card = response.json()
    
    card["capabilities"] = {
        "streaming": False,
        "extensions": [{
            "uri": "https://a2ui.org/a2a-extension/a2ui/v0.8",
            "description": "Ability to render A2UI",
            "required": False,
            "params": {"supportedCatalogIds": ["https://a2ui.org/specification/v0_8/standard_catalog_definition.json"]}
        }]
    }
    card["supportsAuthenticatedExtendedCard"] = True
    
    api_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/collections/default_collection/engines/{app_id}/assistants/default_assistant/agents"
    payload = {
        "name": "store_auditor_a2ui",
        "displayName": "store_auditor_a2ui",
        "description": "An expert A2UI agent that audits store receipts and displays beautiful interactive expense charts.",
        "a2aAgentDefinition": {"jsonAgentCard": json.dumps(card)},
        "authorizationConfig": {"agentAuthorization": os.environ.get("AGENT_AUTHORIZATION")}
    }
    
    print("Registering agent on Gemini Enterprise...")
    resp = requests.post(api_endpoint, headers={**headers, "X-Goog-User-Project": project_id}, json=payload)
    if resp.status_code == 200:
        print("✓ Agent registered successfully!")
        print(resp.json())
    else:
        print(f"✗ Failed: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    main()
