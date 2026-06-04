import requests
from google.auth import default
from google.auth.transport.requests import Request

def main():
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    token = credentials.token
    
    url = "https://global-discoveryengine.googleapis.com/v1alpha/projects/shade-sandbox/locations/global/authorizations"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Goog-User-Project": "shade-sandbox"
    }
    
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    
    import json
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
