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
    engine_id = "3839171897531039744"
    
    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {
        "Authorization": f"Bearer {_get_bearer_token()}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": project_id
    }
    
    filter_query = f'resource.labels.instance_id:"{engine_id}" OR "{engine_id}"'
    
    payload = {
        "resourceNames": [f"projects/{project_id}"],
        "filter": filter_query,
        "orderBy": "timestamp desc",
        "pageSize": 50
    }
    
    print("Fetching Cloud Logging entries via REST API...")
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code == 200:
        entries = resp.json().get("entries", [])
        print(f"Found {len(entries)} log entries:")
        import json
        for entry in entries:
            print(f"--- ENTRY {entry.get('timestamp')} ---")
            print(json.dumps(entry, indent=2))
    else:
        print(f"Failed to fetch logs: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    main()
