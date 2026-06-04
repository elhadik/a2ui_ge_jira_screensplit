---
name: a2ui-hybrid-deployment
description: Professional architectural guide to staging, packaging, deploying, and registering standalone JIRA-integrated A2UI agents on Google Cloud Gemini Enterprise.
---

# A2UI Hybrid Deployment Skill

This guide details the verified engineering patterns, directory structures, code configurations, and lock-bypassing methods required to design, build, test, and deploy fully functional A2UI (Agent-driven User Interface) agents that render rich declarative interactive components in **Google Cloud Gemini Enterprise**.

---

## 🏗️ 1. The Hybrid Directory Layout

### The Problem: Sibling Import & Packaging Clash
*   **Local Runner Emulator (`adk web` / `adk run`)**: Requires your primary entry point file `agent.py` (exposing `root_agent`) to sit flat directly inside the root directory. If nested inside subfolders, the CLI throws `ValueError: No root_agent found`.
*   **Cloud Container Builder (`deploy.py` / Vertex AI)**: Strictly requires that all custom scripts you bundle as `"extra_packages"` be structured inside **subdirectory package folders** (i.e., folders containing python scripts and a blank `__init__.py` file). It does not support individual flat python files.

### The Hybrid Solution
Structure your workspace in a **Hybrid Layout**:
1.  Place all core module scripts (`executor.py`, `tools.py`, `document_parser.py`, `gemini_parser.py`, and the primary implementation `agent.py`) nested inside a dedicated package folder: `agents/store_auditor_agent/`.
2.  Place a tiny, one-line **bridge wrapper `agent.py`** directly at the root level:
    ```python
    from agents.store_auditor_agent.agent import root_agent
    ```
    This bridges the gap: the local CLI immediately finds the root `agent.py`, and the cloud build compiler deploys `agents/store_auditor_agent/` as a clean package module.

---

## 🔄 2. Adaptive Absolute-Relative Import Fallbacks

Because sibling scripts inside the subdirectory are loaded relatively in the local `adk web` playground but loaded globally in flat CLI environments, use **adaptive try-except sibling import fallback loops** inside all your Python scripts:

### 📁 agent.py Sibling Fallback Example
```python
try:
    from .tools import audit_invoice_tool, analyze_uploaded_invoice_tool
except ImportError:
    from tools import audit_invoice_tool, analyze_uploaded_invoice_tool
```

### 📁 tools.py Sibling Fallback Example
```python
try:
    from .document_parser import parse_document
    from .gemini_parser import analyze_receipt_with_gemini
except ImportError:
    from document_parser import parse_document
    from gemini_parser import analyze_receipt_with_gemini
```

### 📁 executor.py Sibling Fallback Example
```python
try:
    from .agent import get_agent
except ImportError:
    from agent import get_agent
```

This robust fallback loop bridges package loaders and flat runners cleanly, preventing any `ModuleNotFoundError` or `attempted relative import with no known parent package` exceptions.

---

## 📥 3. A2A File Part Forwarding in `executor.py`

### The Problem: Discarded File Uploads
When a user uploads or drags-and-drops a file in **Gemini Enterprise chat**, the platform stores the file in GCS and passes the reference inside the incoming A2A request's `context.message.parts`. 

If your executor's `execute()` method only extracts the text query (`context.get_user_input()`) and forwards that to the ADK runner, **the uploaded file is completely discarded**, and the tool will fail with `"Error: No invoice uploaded yet"`.

### The Solution: Forwarding the GCS / Inline File Parts
Use the built-in converter helper `to_stored_part` from the `a2a-sdk` package inside your executor's `execute()` method to dynamically map incoming A2A request parts into Vertex AI GenAI Parts:

```python
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        self._init_agent()

        from a2a.contrib.tasks.vertex_task_converter import to_stored_part
        
        runner_parts = []
        if context.message and context.message.parts:
            for part in context.message.parts:
                try:
                    # Automatically converts TextPart, FilePart (inline or URI), and DataPart
                    runner_parts.append(to_stored_part(part))
                except Exception as e:
                    logger.warning(f"Failed to convert part: {e}")

        # Fallback to standard text query if parts are empty
        if not runner_parts:
            query = context.get_user_input()
            runner_parts.append(types.Part(text=query))

        logger.info(f"StoreAuditorExecutor executing query with {len(runner_parts)} parts")
        
        # ... load session state ...

        # Forward the complete parts list to the runner
        content = types.Content(role='user', parts=runner_parts)
        
        async for event in self.runner.run_async(
            session_id=session.id,
            user_id='user',
            new_message=content
        ):
            # ... process final response events ...
```

---

## 🛡️ 4. Discovery Engine Authorization Lock Bypassing & Registry Lock Preservation

### The Problem: Soft-Delete Resource Cache Locking
When you delete a custom agent in Discovery Engine (or via API curl), the platform marks the agent as deleted. However, the **Authorization Resource** binding (`AGENT_AUTHORIZATION`) remains cached and soft-locked in the cloud background for up to 30 days due to asynchronous soft-deletion locks. 

If you attempt to register a new agent bound to the same authorization ID (e.g., `combined-auth-v27`), the platform rejects it with a `400 FAILED_PRECONDITION: resource is used by another agent` error.

### The Golden Rule: Registry Lock Preservation (CRITICAL)
To avoid locking out all available authorization slots during continuous code updates to the reasoning engine:
* **NEVER delete active agent cards** when updating the reasoning engine logic!
* Instead, perform an **in-place update (PATCH)** on the existing agent card resource name (`projects/<PROJECT_ID>/locations/global/collections/default_collection/engines/<GEMINI_APP_ID>/assistants/default_assistant/agents/<ACTIVE_AGENT_ID>`).
* Pass a `PATCH` request with query parameter `?updateMask=a2aAgentDefinition` to update the inner JSON agent card definition to point to your newly deployed Vertex AI Reasoning Engine container URL. This keeps the active agent card alive, preserves the existing authorization slot lease, and bypasses any soft-delete locks completely!

### The Solution: Programmatic Sequential Slot Incrementation
To completely bypass manual steps or soft-deletion delays, the deployment (`deploy.py`) and registration (`register.py`) pipelines are equipped with **Dynamic Slot Auto-Provisioning**:

1. **Scan Existing Authorizations**: The scripts fetch the complete list of current Discovery Engine authorization slots.
2. **Extract Suffix Versions**: Sift out all slots matching the prefix `combined-auth-v` and extract their version numbers.
3. **Compute Next Slot**: Auto-calculate the next slot name: `combined-auth-v{max_ver + 1}`.
4. **Proactively Provision Slot**: Issue a POST API call to provision the brand new slot utilizing pre-configured client credentials instantly.
5. **Seamless Registration**: Register the agent bound to the newly created slot and automatically sync the `.env` file.

#### The Dynamic Registration Pattern Implementation:
```python
    # 1. Dynamic slot calculation to bypass soft-delete unbinding delay
    auths_url = f"https://global-discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/authorizations"
    auths_resp = requests.get(auths_url, headers=headers)
    auth_slots = [auth["name"].split("/")[-1] for auth in auths_resp.json().get("authorizations", [])]
    
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
    
    # 2. Dynamically create the brand new authorization slot on Discovery Engine
    create_auth_url = f"https://global-discoveryengine.googleapis.com/v1alpha/projects/{project_id}/locations/global/authorizations?authorizationId={target_slot}"
    create_payload = {
        "name": f"projects/{project_id}/locations/global/authorizations/{target_slot}",
        "serverSideOauth2": {
            "clientId": client_id,
            "clientSecret": client_secret,
            "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?...",
            "tokenUri": "https://oauth2.googleapis.com/token"
        }
    }
    requests.post(create_auth_url, headers=headers, json=create_payload)
```

This completely eliminates unbinding delays, letting developers execute deployments and registrations in under 3 seconds with zero manual overhead!

---

## ⚙️ 5. Cloud Environment Variables Configuration

For your GCS routing and JIRA ticketing integration tools to execute successfully inside the serverless Reasoning Engine container, make sure to explicitly forward your `.env` keys inside `deploy.py`'s `"env_vars"` configuration block:

```python
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
```

---

## 🚀 6. Quick Deployment & Registration Guide

### Step 1: Re-stage Sandbox & Verify locally
Make sure port 8000 is free, stage your sandbox, and run local CLI or web playground emulators:
```bash
fuser -k 8000/tcp || true
rm -rf /tmp/adk_agents/GE_fileagent_a2ui && mkdir -p /tmp/adk_agents/GE_fileagent_a2ui
cp -r * /tmp/adk_agents/GE_fileagent_a2ui/
cp .env /tmp/adk_agents/GE_fileagent_a2ui/

# Verify locally
uv run adk run /tmp/adk_agents/GE_fileagent_a2ui "Run store audit..."
```

### Step 2: Deploy Custom Reasoning Engine
Run the deploy command to package and host the Reasoning Engine on Vertex AI:
```bash
uv run deploy.py
```
Copy the provisioned Engine ID (e.g. `3531370214404915200`).

### Step 3: Bind and Register in Gemini Enterprise
Create the sequential authorization slot if needed, update `.env`, and run your registration helper script:
```bash
uv run register.py
```
The agent `store_auditor_a2ui` is now fully functional, active, and rendering rich visual charts in Gemini Enterprise!
