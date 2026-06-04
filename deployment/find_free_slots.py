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
    bearer_token = _get_bearer_token()
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    locations = ["global", "us-central1"]
    slot_map = {}
    
    for loc in locations:
        engines_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/{loc}/collections/default_collection/engines"
        try:
            resp = requests.get(engines_endpoint, headers=headers)
            if resp.status_code == 200:
                engines = resp.json().get("engines", [])
                print(f"Scanning {len(engines)} engines in location '{loc}'...")
                for eng in engines:
                    eng_id = eng["name"].split("/")[-1]
                    display_name = eng.get("displayName")
                    
                    agents_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/{eng['name']}/assistants/default_assistant/agents"
                    try:
                        a_resp = requests.get(agents_endpoint, headers=headers)
                        if a_resp.status_code == 200:
                            agents = a_resp.json().get("agents", [])
                            for agent in agents:
                                agent_id = agent["name"].split("/")[-1]
                                auth_config = agent.get("authorizationConfig", {})
                                auth_slot = auth_config.get("agentAuthorization", "").split("/")[-1]
                                if auth_slot:
                                    slot_map[auth_slot] = {
                                        "location": loc,
                                        "engine_id": eng_id,
                                        "engine_name": display_name,
                                        "agent_id": agent_id,
                                        "agent_name": agent.get("displayName")
                                    }
                    except Exception:
                        pass
        except Exception as e:
            print(f"Failed to list engines in '{loc}': {e}")
            
    print("\n--- BOUND SLOTS MAP ---")
    for slot, info in sorted(slot_map.items()):
        print(f"Slot: {slot} => Bound to Agent '{info['agent_name']}' ({info['agent_id']}) in Engine '{info['engine_name']}' ({info['engine_id']}) [{info['location']}]")

if __name__ == "__main__":
    main()
