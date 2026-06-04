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
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(root_dir, ".env"))
    project_id = os.environ.get("PROJECT_ID")
    app_id = os.environ.get("GEMINI_ENTERPRISE_APP_ID")
    location = os.environ.get("LOCATION")
    
    remote_engine = "projects/943928157761/locations/us-central1/reasoningEngines/5038325667062611968"
    project_number = remote_engine.split("/")[1]
    a2a_endpoint = f"https://{location}-aiplatform.googleapis.com/v1beta1/{remote_engine}/a2a/v1/card"
    
    headers = {"Authorization": f"Bearer {_get_bearer_token()}", "Content-Type": "application/json"}
    
    print("Fetching A2UI agent card from reasoning engine...")
    response = httpx.get(a2a_endpoint, headers=headers, timeout=120.0)
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
    
    print("Dynamically fetching all authorizations from API...")
    auths_url = f"https://global-discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/authorizations"
    auths_resp = requests.get(auths_url, headers={**headers, "X-Goog-User-Project": project_id})
    auths_resp.raise_for_status()
    auth_slots = [auth["name"].split("/")[-1] for auth in auths_resp.json().get("authorizations", [] if auths_resp.json() else [])]
    # Dynamic slot calculation & auto-creation to bypass soft-delete unbinding delay
    combined_versions = []
    for slot in auth_slots:
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
    
    # Create the brand new authorization slot on Discovery Engine
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
    
    create_resp = requests.post(create_auth_url, headers={**headers, "X-Goog-User-Project": project_id}, json=create_payload)
    if create_resp.status_code in (200, 201):
        print(f"✓ Authorization slot '{target_slot}' created successfully!")
    else:
        print(f"  - Note/Status when ensuring slot exists: {create_resp.status_code} - {create_resp.text}")
        
    auth_uri = f"projects/{project_number}/locations/global/authorizations/{target_slot}"
    payload = {
        "name": "store_auditor_a2ui_v2",
        "displayName": "store_auditor_a2ui_v2",
        "description": "An expert A2UI agent that audits store receipts and displays beautiful interactive expense charts.",
        "a2aAgentDefinition": {"jsonAgentCard": json.dumps(card)},
        "authorizationConfig": {"agentAuthorization": auth_uri}
    }
    
    import time
    registered_success = False
    for attempt in range(1, 6):
        print(f"Attempt {attempt}/5: Attempting registration with slot '{target_slot}'...")
        resp = requests.post(api_endpoint, headers={**headers, "X-Goog-User-Project": project_id}, json=payload)
        if resp.status_code == 200:
            print(f"✓ Agent registered successfully under slot: {target_slot}!")
            print(resp.json())
            
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
                print(f"✓ Synced AGENT_AUTHORIZATION in .env to {target_slot}!")
            
            registered_success = True
            break
        else:
            err_msg = resp.json().get("error", {}).get("message", "")
            print(f"  - Attempt {attempt} failed: {resp.status_code} - {err_msg}")
            if "is used by another agent" in err_msg and attempt < 5:
                print("  - Slot is still locked by cache. Sleeping 30s before next retry...")
                time.sleep(30)
            else:
                break
                
    if not registered_success:
        print(f"✗ Error: Failed to acquire slot '{target_slot}' after 5 attempts.")

if __name__ == "__main__":
    main()
