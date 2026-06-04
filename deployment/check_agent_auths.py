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
    
    # 1. List all engines in the project
    engines_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/collections/default_collection/engines"
    bearer_token = _get_bearer_token()
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    resp = requests.get(engines_endpoint, headers=headers)
    resp.raise_for_status()
    engines = resp.json().get("engines", [])
    
    print(f"Scanning {len(engines)} engines for registered agents and authorizations...")
    
    for eng in engines:
        eng_name = eng["name"]
        eng_id = eng_name.split("/")[-1]
        display_name = eng.get("displayName")
        solution_type = eng.get("solutionType")
        
        # 2. Query agents for each engine (Solution types CHAT or SEARCH often host assistants/agents)
        agents_endpoint = f"https://discoveryengine.googleapis.com/v1alpha/{eng_name}/assistants/default_assistant/agents"
        print(f" - Scanning Engine: {eng_id} ({display_name}) | Solution Type: {solution_type}")
        try:
            agents_resp = requests.get(agents_endpoint, headers=headers)
            print(f"   Status Code: {agents_resp.status_code}")
            if agents_resp.status_code == 200:
                agents = agents_resp.json().get("agents", [])
                print(f"   Found {len(agents)} agent(s).")
                if agents:
                    for agent in agents:
                        import json
                        print(f"     - Agent ID: {agent['name'].split('/')[-1]}")
                        print(f"       Raw Agent: {json.dumps(agent, indent=2)}")
            elif agents_resp.status_code == 404:
                pass
            else:
                print(f"     Error querying agents: {agents_resp.status_code}")
        except Exception as e:
            print(f"     Query failed: {e}")

if __name__ == "__main__":
    main()
