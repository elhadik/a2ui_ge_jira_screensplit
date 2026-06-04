import os
import requests
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
    
    # The latest active agent ID we just registered
    active_agent_id = "13541023652281796167"
    
    api_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/collections/default_collection/engines/{app_id}/assistants/default_assistant/agents"
    
    bearer_token = _get_bearer_token()
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    print("Fetching all registered agents...")
    resp = requests.get(api_endpoint, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    agents = data.get("agents", [])
    print(f"Found {len(agents)} registered agent(s).")
    
    deleted_count = 0
    for agent in agents:
        agent_resource_name = agent["name"]
        agent_id = agent_resource_name.split("/")[-1]
        display_name = agent.get("displayName", "")
        description = agent.get("description", "")
        
        print(f"\nAgent ID: {agent_id}")
        print(f" - Display Name: {display_name}")
        print(f" - Description: {description}")
        print(f" - Resource Name: {agent_resource_name}")
        
        # Check if it's a redundant store_auditor_a2ui agent
        if display_name in ("store_auditor_a2ui", "store_auditor_a2ui_v2") and agent_id != active_agent_id:
            print(f"⚠️ Found redundant agent '{agent_id}'. Deleting...")
            delete_url = f"https://discoveryengine.googleapis.com/v1alpha/{agent_resource_name}"
            del_resp = requests.delete(delete_url, headers=headers)
            if del_resp.status_code in [200, 204]:
                print(f"✓ Successfully deleted agent '{agent_id}'!")
                deleted_count += 1
            else:
                print(f"✗ Failed to delete agent '{agent_id}': {del_resp.status_code}")
                print(del_resp.text)
        elif agent_id == active_agent_id:
            print("🟢 Keeping active agent (Latest Working Version).")
        else:
            print("⚪ Keeping other registered agent.")
            
    print("\n" + "="*40)
    print(f"Cleanup complete. Redundant agents deleted: {deleted_count}")
    print("="*40)

if __name__ == "__main__":
    main()
