---
name: adk-enterprise-file-reader
description: Guides the creation of plain ADK agents deployed to Vertex AI Reasoning Engine that natively read files uploaded in Gemini Enterprise without A2A/A2UI.
---

# ADK Enterprise Native File Reader Skill

This global skill guides the design and implementation of plain Google Agent Development Kit (ADK) agents that natively process user-uploaded files (images, PDFs, spreadsheets, text files) inside the Gemini Enterprise chat assistant interface, **completely bypassing any need for complex A2A or A2UI custom frontend rendering widgets.**

---

## 🏗️ Architectural Concept (How it works)

When a user attaches or uploads a file in the standard Gemini Enterprise chat console:
1.  Gemini Enterprise automatically uploads the file asset to a secure, system-managed Google Cloud Storage (GCS) bucket.
2.  It injects the file metadata directly into the chat session history event as a `Part` containing `file_data` with a GCS URI (`gs://...`).
3.  Instead of building a custom A2A/A2UI React widget to parse/upload the file, a plain ADK agent can **programmatically scan and parse the session history** inside a standard Python `FunctionTool`!

---

## 🛠️ Implementation Workflow

Follow these steps to build a native file-reading plain ADK agent:

### Step 1: Declare an Asynchronous Function Tool
Create an asynchronous tool function (`async def`) that requests `tool_context` to access the active session and GCS client:

```python
import os
import json
from google.adk.tools import FunctionTool
from google.cloud import storage
from google.genai import types

async def analyze_uploaded_file_tool(tool_context=None) -> str:
    """Programmatically retrieves and parses the user's uploaded document from session history."""
    if not tool_context:
        return "Error: No tool context available."

    part = None
    filename = "uploaded_document"

    # 1. Scan staged session artifacts
    artifact_keys = await tool_context.list_artifacts()
    if artifact_keys:
        filename = artifact_keys[-1]
        part = await tool_context.load_artifact(filename)

    # 2. Fallback: Traverse session history events for any file parts uploaded by the user
    if not part:
        session_events = tool_context.session.events
        for event in reversed(session_events):
            if event.author == "user" and event.content and event.content.parts:
                for p in event.content.parts:
                    if p.inline_data or p.file_data:
                        part = p
                        break
            if part:
                break

    if not part:
        return "Error: No document uploaded yet. Please attach or upload a file first."

    # 3. Download the document content in-memory from GCS
    data_bytes = None
    mime_type = "application/pdf"

    if part.inline_data:
        mime_type = part.inline_data.mime_type
        data_bytes = part.inline_data.data
    elif part.file_data and part.file_data.file_uri:
        mime_type = part.file_data.mime_type
        file_uri = part.file_data.file_uri
        
        # ADC Auth: Uses GCS Client under reasoning engine metadata credentials
        try:
            client = storage.Client()
            if file_uri.startswith("gs://"):
                path_parts = file_uri[5:].split("/", 1)
                bucket_name = path_parts[0]
                blob_name = path_parts[1]
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                data_bytes = blob.download_as_bytes()
        except Exception as e:
            return f"Error: Failed to download asset from GCS: {e}"

    if not data_bytes:
        return "Error: Failed to read file contents."

    # 4. Pass bytes directly to your specialized extraction or OCR parsing logic
    # (e.g. client.models.generate_content(contents=[Part.from_bytes(data=data_bytes, mime_type=mime_type)]))
    return f"Successfully loaded {filename} ({mime_type}) with size {len(data_bytes)} bytes."
```

### Step 2: Expose the Tool to the Root Agent
Wrap the async tool inside a standard `FunctionTool` and bind it to your lead orchestrator:

```python
from google.adk.agents import Agent
from google.adk.tools import load_artifacts

orchestrator_agent = Agent(
    name="orchestrator",
    model="gemini-2.5-flash",
    instruction="""Coordinate store auditing. 
    When the user uploads a file, you must call the `analyze_uploaded_file_tool` tool 
    to retrieve the file and parse its content.""",
    tools=[load_artifacts, FunctionTool(analyze_uploaded_file_tool)]
)

root_agent = orchestrator_agent
```

---

## ☁️ Deployment, Registration & Registry Lock Preservation

### Step 1: Deploy package to Vertex AI Agent Engine
Package and host your Python code on Vertex AI Reasoning Engine:
```bash
export GOOGLE_API_USE_CLIENT_CERTIFICATE=false
adk deploy agent_engine <package_folder> --project <GCP_PROJECT_ID> --region us-central1
```
This will return your deployed Reasoning Engine Resource Name (e.g., `projects/<PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<ENGINE_ID>`).

### Step 2: Register as a Custom Agent in Discovery Engine
To bind this Reasoning Engine to Gemini Enterprise so it is available to users in the chat console:
1. Retrieve or provision a Google OAuth authorization slot (e.g., `google-auth-v1`).
2. Create/POST the agent card using the Discovery Engine Agents API, specifying the `adkAgentDefinition` and binding it to the authorization slot in the `authorizationConfig`.

### Step 3: Registry Lock Preservation Rule (CRITICAL)
To protect your GCP project from running out of available OAuth slots during normal developer code iterations:
* **NEVER delete active agent cards** when updating the Python container logic. In Discovery Engine, deleting an agent card releases the slot binding but keeps it cached in a 30-day soft-delete lock, making it completely unusable for subsequent registrations.
* **The Solution**: Perform **in-place updates (PATCH)** against the active agent resource name:
  ```bash
  # Update the agent card in-place using PATCH and specifying updateMask
  PATCH https://discoveryengine.googleapis.com/v1alpha/projects/<PROJECT_ID>/locations/global/collections/default_collection/engines/<GEMINI_APP_ID>/assistants/default_assistant/agents/<ACTIVE_AGENT_ID>?updateMask=adkAgentDefinition
  ```
  This keeps your slot lease alive and dynamically binds the active agent to your new Reasoning Engine version instantly.

### Step 4: Interactive Testing
1. Open your browser and navigate to your Gemini Enterprise Chat console.
2. Locate your custom agent under the **"From your organization"** tab.
3. Start a new conversation and upload/attach any document (PDF, CSV, Image).
4. Ask the agent: *"Analyze this uploaded document."*
5. The agent will execute natively inside the default text pane, parsing the document with zero custom UI widgets required!

---
