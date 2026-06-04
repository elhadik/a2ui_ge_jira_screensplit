---
name: a2ui-widgets
description: Guides the creation, deployment, and registration of A2UI agents on Gemini Enterprise.
---
# A2UI Widgets Skill

This skill provides instructions and patterns for developing, deploying, and registering AI agents that use the A2UI (Agent-to-Agent User Interface) protocol to render rich components in Google Cloud Gemini Enterprise.

## Key Concepts
- **A2A Protocol**: The communication protocol between Gemini Enterprise and custom agents.
- **A2UI Extension**: The extension that allows agents to send structured UI data (JSON) to be rendered by the host application.

## Implementation Workflow

### 1. Agent Definition
- Use `google.adk.agents.Agent` or `LlmAgent` to define the agent.
- Use `A2uiSchemaManager` to generate the system prompt with the correct schema and examples.
- Wrap the UI data in `<a2ui-json>` and `</a2ui-json>` tags in the agent's output.

### 2. Executor Definition
- Create an `AgentExecutor` that handles the A2A protocol.
- Parse the agent's output to extract A2UI JSON and deliver it via `TaskUpdater`.
- Handle UI events (like clicks) if applicable.

### 3. Deployment and Registration
- Use `vertexai.Client` and `client.agent_engines.create` to deploy to Agent Engine.
- Obtain a unique **Authorization Resource** in Gemini Enterprise (Discovery Engine) using a `curl` command with OAuth credentials.
- Register the agent in Gemini Enterprise with the A2UI capability extension enabled in the agent card.

## Split-Screen / Multi-Surface Rendering Pattern
Gemini Enterprise supports split-screen interfaces by rendering multiple A2UI surfaces side-by-side or stacked.
To implement this, your agent MUST output a flat list of actions (e.g., `beginRendering` and `surfaceUpdate`) for all surfaces combined inside a single `<a2ui-json>` block.

### Pattern Example
- **Surface 1 (Inline Card)**: A `VegaChart` rendering an interactive chart.
- **Surface 2 (Side-Panel Details)**: A `WebFrameSrcdoc` rendering an audit table and download capabilities.

```json
[
  { "beginRendering": { "surfaceId": "my-agent-chart", "root": "chart-root" } },
  { "surfaceUpdate": {
      "surfaceId": "my-agent-chart",
      "components": [ ... ]
  } },
  { "beginRendering": { "surfaceId": "my-agent-details", "root": "details-root" } },
  { "surfaceUpdate": {
      "surfaceId": "my-agent-details",
      "components": [ ... ]
  } }
]
```

## WebFrameSrcdoc Schema Rules & Security Policies
When utilizing the `WebFrameSrcdoc` component to render custom HTML, you MUST strictly follow the official A2UI component schema and security rules:

1. **Direct Root Layout (CRITICAL)**: To prevent black/blank screens in sandboxed sidebar panels inside Gemini Enterprise, `WebFrameSrcdoc` MUST be returned directly as the **root component** inside your `surfaceUpdate` (flattened structure). Avoid wrapping it in nested layout components like `Card`, `Column`, `Row`, or `Button`.
2. **Official Properties Only**: The `WebFrameSrcdoc` component mapping supports exactly TWO properties:
   - `"htmlContent"`: A StringValue reference containing the entire custom HTML page: `{ "literalString": "...html..." }`.
   - `"height"`: A raw numeric value representing the pixel height (e.g. `400` or `500`).
   - **CRITICAL RULE**: Do NOT output properties like `"srcdoc"`, `"sandbox"`, or `"style"` inside the `WebFrameSrcdoc` component block. They violate the component contract, are completely ignored by the renderer, and will trigger validation/security exceptions.

3. **Mandatory CSP Meta Tag Formatting**: To satisfy platform-level JSON regex filters, your HTML head MUST include the CSP meta tag formatted exactly as follows:
   ```html
   <meta content="connect-src 'none'" http-equiv="Content-Security-Policy">
   ```
   - **Do NOT** include any semicolons (`;`) inside the `content` attribute value (i.e. do not use `'none';`). Semicolons will cause the platform's security filter regex to fail, blocking the UI element.

4. **Strict Quote Escaping Rules (CRITICAL)**:
   - Retain double quotes (`"`) strictly for the attributes of the mandatory CSP tag: `<meta content="connect-src 'none'" http-equiv="Content-Security-Policy">`.
   - Use single quotes (`'`) for **all other** HTML attributes, inline styles, CSS property rules, and JavaScript strings inside the HTML page to prevent JSON parsing errors.

5. **Sandbox Clipboard Fallback**: Since Gemini Enterprise chat components render in secure sandboxed iframes, standard browser file downloads may be blocked or restricted by security filters. 
   - **Rule**: ALWAYS implement copy-to-clipboard controls as a primary fallback mechanism!
   - Provide a copy button: `<button id='copyBtn' onclick='copyCSV()'>Copy CSV Data</button>`
   - Provide a show/hide button: `<button onclick='toggleRaw()'>Show/Hide Raw CSV</button>`
   - Include a hidden textarea containing the raw CSV or structured data string: `<textarea id='csvText' style='display: none;'>...</textarea>`
   - Implement lightweight JS in your widget `<script>` block:
     ```javascript
     function copyCSV() {
       const text = document.getElementById('csvText').value;
       navigator.clipboard.writeText(text).then(() => {
         const btn = document.getElementById('copyBtn');
         btn.textContent = '✓ Copied!';
         setTimeout(() => { btn.textContent = 'Copy CSV Data'; }, 2000);
       });
     }
     function toggleRaw() {
       const area = document.getElementById('csvText');
       area.style.display = area.style.display === 'none' || !area.style.display ? 'block' : 'none';
     }
     ```

6. **Trusted Types & Dynamic DOM Updates (CRITICAL)**: Gemini Enterprise enforces strict Trusted Types policies. Setting `.innerHTML` directly with template strings inside the sandboxed iframe will trigger CSP Trusted Types violation errors and block rendering.
   - **Rule**: Implement a Trusted Types policy builder and fall back to `DOMParser` for all dynamic DOM assignments inside your widget script:
     ```javascript
     var policy = null;
     if (window.trustedTypes && window.trustedTypes.createPolicy) {
         try {
             policy = window.trustedTypes.createPolicy('a2ui-policy', {
                 createHTML: function(s) { return s; }
             });
         } catch (e) {
             try {
                 policy = window.trustedTypes.createPolicy('default', {
                     createHTML: function(s) { return s; }
                 });
             } catch (e2) {
                 console.warn('TrustedTypes policy creation failed:', e2);
             }
         }
     }

     function clearElement(element) {
         while (element.firstChild) {
             element.removeChild(element.firstChild);
         }
     }

     function setHTML(element, htmlString) {
         if (policy && typeof policy.createHTML === 'function') {
             try {
                 element.innerHTML = policy.createHTML(htmlString);
                 return;
             } catch (err) {
                 console.warn('TrustedHTML assignment failed, falling back to DOMParser:', err);
             }
         }
         clearElement(element);
         try {
             var parser = new DOMParser();
             var doc = parser.parseFromString(htmlString, 'text/html');
             while (doc.body.firstChild) {
                 element.appendChild(doc.body.firstChild);
             }
         } catch (fallbackErr) {
             console.error('DOMParser fallback failed:', fallbackErr);
             element.innerHTML = htmlString;
         }
     }
     ```

## Building a Custom HTML Widget with WebFrameSrcdoc
To construct a fully interactive custom HTML widget (e.g., a side-panel details table with download capabilities), follow this structural template:

### 1. Complete HTML Skeleton Template
```html
<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'>
  <meta content="connect-src 'none'" http-equiv="Content-Security-Policy">
  <title>Preview Card</title>
  <style>
    body { font-family: sans-serif; padding: 20px; color: #f8fafc; background-color: #0f172a; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    th, td { padding: 10px; border: 1px solid #334155; text-align: left; }
    th { background-color: #1e293b; }
    button { background-color: #1a73e8; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 14px; }
    button:hover { background-color: #1557b0; }
  </style>
</head>
<body>
  <h3>Audit Report & Breakdown Details</h3>
  <table>
    <thead>
      <tr><th>Item</th><th>Qty</th><th>Price</th><th>Amount</th></tr>
    </thead>
    <tbody>
      <!-- Rows dynamically populated by agent or template substitution -->
      <tr><td>GAL WHOLE MILK</td><td>1</td><td>4.29</td><td>4.29</td></tr>
    </tbody>
  </table>
  <button onclick='downloadCSV()'>Download Audit Data (CSV)</button>
  <script>
    function downloadCSV() {
      const csv = 'Item,Qty,Price,Amount\nGAL WHOLE MILK,1,4.29,4.29';
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit_report.csv';
      a.click();
    }
  </script>
</body>
</html>
```

### 2. Best Practices for HTML Widget Generation
- **Script-Free Initial Bootstrap (CRITICAL)**: When deploying/testing a new card configuration for the first time, always begin with a completely static, script-free HTML structure (no `<script>` tags, no dynamic `window.INJECTED_DATA` bindings, no `onload` event handlers). This allows you to verify that the iframe and styling render correctly without clashing with iframe sandbox/postMessage restrictions. Once rendering is confirmed healthy, gradually re-integrate dynamic script logic.
- **CSS & Styling**: Always write self-contained `<style>` rules in the `<head>`. Since widgets are rendered in a sandboxed shadow iframe, they do not inherit host styles.
- **Self-Contained JavaScript**: Implement any client-side logic (e.g. sorting tables, toggling details, or triggering downloads) in inline `<script>` blocks inside the `<body>`.
- **Dynamic Downloads**: To enable downloading data (e.g. raw CSV or JSON), package your structured string into a `Blob` (mime type `'text/csv'` or `'application/json'`), create a temporal object URL using `URL.createObjectURL`, programmatically create and append an `<a>` tag, assign the URL, and call `.click()`. The browser's sandboxed iframe will allow this download sequence natively.
- **Strict Quote Escaping**: Always use single quotes (`'`) inside your HTML block for attributes and JavaScript strings to guarantee that JSON-nesting doesn't corrupt the A2UI payload structure. Use double quotes (`"`) ONLY for attributes of the mandatory CSP tag.

## Registry Lock Preservation (PATCH) & Pruning
* **Registry Lock Preservation**: NEVER delete active agent cards during normal container code updates! Deleting the agent card releases the authorization slot lease and places the slot in a 30-day soft-delete lock state. 
  - To deploy new container logic, issue an in-place **`PATCH` request** against the active agent resource name with `?updateMask=a2aAgentDefinition` to update the agent card to point to your new Vertex AI Reasoning Engine container URL.
* **Registry Pruning**: When clean-ups are required, use a pruning script (such as `list_and_delete_agents.py`) to scan all engines, verify agent IDs, and run a `DELETE` call to clean up actual redundant cards.

## Programmatic Python Authorization Slot Provisioner
To bypass soft-deletion slot locks instantly, create the next sequential authorization slot using Python:
```python
import requests
from google.auth import default
from google.auth.transport.requests import Request

def create_auth(auth_id, client_id, client_secret):
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    token = credentials.token
    
    url = f"https://global-discoveryengine.googleapis.com/v1alpha/projects/<PROJECT_ID>/locations/global/authorizations?authorizationId={auth_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Goog-User-Project": "<PROJECT_ID>"
    }
    
    data = {
        "name": f"projects/<PROJECT_ID>/locations/global/authorizations/{auth_id}",
        "serverSideOauth2": {
            "clientId": client_id,
            "clientSecret": client_secret,
            "authorizationUri": f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&include_granted_scopes=true&response_type=code&access_type=offline&prompt=consent",
            "tokenUri": "https://oauth2.googleapis.com/token"
        }
    }
    
    resp = requests.post(url, headers=headers, json=data)
    print(f"Created slot {auth_id}: status={resp.status_code}")

create_auth("combined-auth-v37", "<CLIENT_ID>", "<CLIENT_SECRET>")
```

