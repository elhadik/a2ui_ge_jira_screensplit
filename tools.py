# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os

logger = logging.getLogger(__name__)

try:
    from .components import _LAST_ANALYSIS_RESULTS, generate_audit_a2ui_dashboard_tool
except ImportError:
    from components import _LAST_ANALYSIS_RESULTS, generate_audit_a2ui_dashboard_tool





def extract_data_tool(file_path: str = None, data_bytes: bytes = None, mime_type: str = "application/pdf") -> str:
    """Parses the invoice/receipt document to extract key entities and line items."""
    try:
        from .document_parser import parse_document
    except ImportError:
        from document_parser import parse_document
    data = parse_document(file_path=file_path, data_bytes=data_bytes, mime_type=mime_type)
    return json.dumps(data)

def validate_data_tool(file_path: str = None, data_bytes: bytes = None, mime_type: str = "application/pdf", extraction_results_json: str = "{}") -> str:
    """Validates the extracted entities against the original document image/PDF."""
    try:
        from .gemini_parser import analyze_receipt_with_gemini
    except ImportError:
        from gemini_parser import analyze_receipt_with_gemini
    extraction_results = json.loads(extraction_results_json)
    data = analyze_receipt_with_gemini(file_path=file_path, data_bytes=data_bytes, document_ai_result=extraction_results, mime_type=mime_type)
    return json.dumps(data)

def route_document_tool(filename: str, mime_type: str, score: int, data_bytes: bytes = None, file_path: str = None) -> str:
    """Routes the processed document to the GCS bucket depending on the score."""
    from google.cloud import storage
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
    processed_bucket_name = os.environ.get("NESS_PROCESSED_DOCS_BUCKET") or "shade-sandbox-processed"
    review_bucket_name = os.environ.get("NESS_HUMAN_REVIEW_BUCKET") or "shade-sandbox-review"
    
    routing_status = "Skipped"
    bucket_name = None
    
    if project_id and processed_bucket_name and review_bucket_name:
        try:
            client = storage.Client(project=project_id)
            bucket_name = processed_bucket_name if score == 3 else review_bucket_name
            bucket = client.bucket(bucket_name)
            
            blob = bucket.blob(filename)
            if data_bytes:
                blob.upload_from_string(data_bytes, content_type=mime_type)
            elif file_path:
                blob.upload_from_filename(file_path, content_type=mime_type)
            
            routing_status = "Success"
            logger.info(f"Routed {filename} to GCS bucket: {bucket_name}")
        except Exception as gcs_e:
            logger.error(f"GCS Routing Error: {gcs_e}")
            routing_status = f"Error: {gcs_e}"
    else:
        logger.warning("Warning: Missing GCS Env Variables. Routing skipped.")
        routing_status = "Missing Config"
        
    return json.dumps({
        "status": routing_status,
        "bucket": bucket_name,
        "score": score
    })

def create_jira_ticket_tool(summary: str, description: str) -> str:
    """Creates a support ticket in JIRA via Atlassian API integration.
    
    Args:
        summary: Brief title of the JIRA ticket.
        description: Detailed description of the issue/discrepancy.
    """
    from atlassian import Jira
    email = os.environ.get("JIRA_EMAIL", "elhadik@google.com")
    api_token = os.environ.get("JIRA_API_TOKEN")
    jira_url = "https://google-team-vwhbosar.atlassian.net"
    
    if not api_token:
        return "Error: JIRA_API_TOKEN environment variable is not set."
        
    try:
        jira = Jira(
            url=jira_url,
            username=email,
            password=api_token,
            cloud=True
        )
        issue = jira.issue_create(
            fields={
                'project': {'key': 'KAN'},
                'summary': summary,
                'description': description,
                'issuetype': {'name': 'Task'}
            }
        )
        return f"Success! Created JIRA issue: {issue.get('key')}"
    except Exception as e:
        return f"Error creating JIRA issue directly: {e}"

def audit_invoice_tool(file_path: str = None, data_bytes: bytes = None, mime_type: str = "application/pdf") -> str:
  """Runs the full invoice/receipt auditing pipeline (extract, validate, route to GCS, log JIRA tickets) and returns the final JSON string containing line items, taxes, routing status, and ticketing info.

  Args:
      file_path: The local absolute path to the invoice/receipt file (PDF or Image).
      data_bytes: Optional in-memory byte content of the document.
      mime_type: The MIME type of the document (e.g., 'application/pdf', 'image/png').
  """
  # Auto-detect MIME type from file extension if left as default
  if file_path and mime_type == "application/pdf":
      ext = os.path.splitext(file_path)[1].lower()
      if ext == ".png":
          mime_type = "image/png"
      elif ext in [".jpg", ".jpeg"]:
          mime_type = "image/jpeg"
      elif ext == ".pdf":
          mime_type = "application/pdf"

  logger.info("--- TOOL CALLED: audit_invoice_tool ---")
  logger.info(f"  - File Path: {file_path}")
  logger.info(f"  - MIME Type: {mime_type}")

  try:
      from .document_parser import parse_document
      from .gemini_parser import analyze_receipt_with_gemini
  except ImportError:
      from document_parser import parse_document
      from gemini_parser import analyze_receipt_with_gemini
  from google.cloud import storage

  # 1. Extract Data
  logger.info("[Audit Tool] Extracting data via Document AI/multimodal OCR...")
  extracted_data = parse_document(file_path=file_path, data_bytes=data_bytes, mime_type=mime_type)

  # 2. Validate Data
  logger.info("[Audit Tool] Assesing accuracy via Gemini visual comparisons...")
  validation_data = analyze_receipt_with_gemini(file_path=file_path, data_bytes=data_bytes, document_ai_result=extracted_data, mime_type=mime_type)

  # 3. GCS Routing
  project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
  processed_bucket_name = os.environ.get("NESS_PROCESSED_DOCS_BUCKET") or "shade-sandbox-processed"
  review_bucket_name = os.environ.get("NESS_HUMAN_REVIEW_BUCKET") or "shade-sandbox-review"
  score = validation_data.get("confidence_score", 0)
  
  routing_status = "Skipped"
  bucket_name = None
  filename = os.path.basename(file_path) if file_path else "uploaded_invoice"

  if project_id and processed_bucket_name and review_bucket_name:
      try:
          client = storage.Client(project=project_id)
          bucket_name = processed_bucket_name if score == 3 else review_bucket_name
          bucket = client.bucket(bucket_name)
          
          blob = bucket.blob(filename)
          if data_bytes:
              blob.upload_from_string(data_bytes, content_type=mime_type)
          elif file_path:
              blob.upload_from_filename(file_path, content_type=mime_type)
          
          routing_status = "Success"
          logger.info(f"[Audit Tool] Routed {filename} to GCS bucket: {bucket_name}")
      except Exception as gcs_e:
          logger.error(f"[Audit Tool] GCS Routing Error: {gcs_e}")
          routing_status = f"Error: {gcs_e}"
  else:
      logger.warning("[Audit Tool] Missing GCS configuration. Routing skipped.")
      routing_status = "Missing Config"

  routing_data = {
      "status": routing_status,
      "bucket": bucket_name,
      "score": score
  }

  # 4. JIRA Ticketing if score < 3
  jira_status = "Skipped (Perfect Score)"
  if score < 3:
      logger.info(f"[Audit Tool] Low audit score ({score}). Creating JIRA ticket...")
      from atlassian import Jira
      email = os.environ.get("JIRA_EMAIL", "elhadik@google.com")
      api_token = os.environ.get("JIRA_API_TOKEN")
      jira_url = "https://google-team-vwhbosar.atlassian.net"
      
      if api_token:
          try:
              jira = Jira(url=jira_url, username=email, password=api_token, cloud=True)
              discrepancy_details = validation_data.get("criteria_met", "Validation discrepancies found.")
              issue = jira.issue_create(
                  fields={
                      'project': {'key': 'KAN'},
                      'summary': f"AUDIT FAIL: Discrepancy in store auditor {filename}",
                      'description': f"Automated store auditor detected discrepancies.\n\nAudit details:\n{discrepancy_details}",
                      'issuetype': {'name': 'Task'}
                  }
              )
              jira_status = f"Success! Created JIRA issue: {issue.get('key')}"
              logger.info(f"[Audit Tool] JIRA Ticket Created: {jira_status}")
          except Exception as e:
              logger.error(f"[Audit Tool] Error creating JIRA issue: {e}")
              jira_status = f"Error: {e}"
      else:
          logger.warning("[Audit Tool] Missing JIRA token. Ticketing skipped.")
          jira_status = "Missing Credentials"

  # 5. Synthesize final payload
  payload = extracted_data
  payload["gemini_analysis"] = validation_data
  payload["gcs_routing"] = routing_data
  payload["jira_ticketing"] = jira_status

  _LAST_ANALYSIS_RESULTS.clear()
  _LAST_ANALYSIS_RESULTS.update(payload)

  # Auto-generate the premium dashboard UI block in-memory
  a2ui_block = generate_audit_a2ui_dashboard_tool(json.dumps(payload))
  
  combined_output = f"Analysis Results:\n{json.dumps(payload, indent=2)}\n\nDashboard UI Block:\n{a2ui_block}"
  return combined_output




async def analyze_uploaded_invoice_tool(tool_context=None) -> str:
  """Finds the user's uploaded invoice or receipt file in the session context and runs the full store auditing and expense pie-chart pipeline on it completely in-memory.

  Only call this tool when the user has uploaded or dragged-and-dropped an image/PDF file into the session.
  """
  if not tool_context:
      return "Error: No tool context available."
      
  part = None
  filename = None
  
  # 1. Try listing formal artifacts (staged uploads)
  artifact_keys = await tool_context.list_artifacts()
  if artifact_keys:
      filename = artifact_keys[-1]
      part = await tool_context.load_artifact(filename)
  
  # 2. Fallback: Search the session history events for any file part sent by the user
  if not part:
      session_events = tool_context.session.events
      for event in reversed(session_events):
          if event.author == "user" and event.content and event.content.parts:
              for p in event.content.parts:
                  if p.inline_data or p.file_data:
                      part = p
                      filename = "uploaded_document"
                      logger.info(f"[Audit Tool] Found file part in user message history: {filename}")
                      break
          if part:
              break
              
  if not part:
      return "Error: No invoice uploaded yet. Please upload or drag-and-drop a file or image first."
      
  mime_type = "application/pdf"
  data_bytes = None
  
  if part.inline_data:
      mime_type = part.inline_data.mime_type
      data_bytes = part.inline_data.data
  elif part.file_data and part.file_data.file_uri:
      mime_type = part.file_data.mime_type
      file_uri = part.file_data.file_uri
      logger.info(f"[Audit Tool] Loading GCS artifact: {file_uri}")
      
      from google.cloud import storage
      try:
          client = storage.Client()
          if file_uri.startswith("gs://"):
              path_parts = file_uri[5:].split("/", 1)
              bucket_name = path_parts[0]
              blob_name = path_parts[1]
              bucket = client.bucket(bucket_name)
              blob = bucket.blob(blob_name)
              data_bytes = blob.download_as_bytes()
      except Exception as gcs_read_e:
          return f"Error: Failed to download artifact from GCS: {gcs_read_e}"
          
  if not data_bytes:
      return f"Error: Failed to load data content for file {filename}."
      
  # 3. Run the audit pipeline completely in-memory (No temporary files!)
  logger.info(f"[Audit Tool] Analyzing uploaded file in-memory: {filename} ({mime_type})")
  result = run_adk_orchestrator(filename=filename, mime_type=mime_type, data_bytes=data_bytes)
  
  _LAST_ANALYSIS_RESULTS.clear()
  _LAST_ANALYSIS_RESULTS.update(result)
  
  # Auto-generate the premium dashboard UI block in-memory
  a2ui_block = generate_audit_a2ui_dashboard_tool(json.dumps(result))
  
  combined_output = f"Analysis Results:\n{json.dumps(result, indent=2)}\n\nDashboard UI Block:\n{a2ui_block}"
  return combined_output




def run_adk_orchestrator(filename: str, mime_type: str, data_bytes: bytes = None, file_path: str = None) -> dict:
    """Triggers the sequential multi-agent pipeline to analyze, audit, and route the invoice."""
    # 1. Extract Data
    logger.info("[Orchestrator] Delegating to Data Extraction logic...")
    extracted_json = extract_data_tool(file_path=file_path, data_bytes=data_bytes, mime_type=mime_type)
    extracted_data = json.loads(extracted_json)
    
    # 2. Validate Data
    logger.info("[Orchestrator] Delegating to Validation logic...")
    validation_json = validate_data_tool(file_path=file_path, data_bytes=data_bytes, mime_type=mime_type, extraction_results_json=extracted_json)
    validation_data = json.loads(validation_json)
    
    # 3. Score & Route Document
    logger.info("[Orchestrator] Delegating to Routing logic...")
    score = validation_data.get("confidence_score", 0)
    routing_json = route_document_tool(filename=filename, mime_type=mime_type, score=score, data_bytes=data_bytes, file_path=file_path)
    routing_data = json.loads(routing_json)
    
    # 4. Trigger JIRA Ticketing if score is below 3 (discrepancy found!)
    jira_status = "Skipped (Perfect Score)"
    if score < 3:
        logger.info(f"[Orchestrator] Low audit score ({score}). Triggering JIRA ticket creation...")
        discrepancy_details = validation_data.get("criteria_met", "Validation discrepancies found.")
        jira_status = create_jira_ticket_tool(
            summary=f"AUDIT FAIL: Discrepancy in store auditor {filename}",
            description=f"Automated store auditor detected discrepancies.\n\nAudit details:\n{discrepancy_details}"
        )
        logger.info(f"[Orchestrator] JIRA Ticket: {jira_status}")
        
    # 5. Synthesize final payload
    payload = extracted_data
    payload["gemini_analysis"] = validation_data
    payload["gcs_routing"] = routing_data
    payload["jira_ticketing"] = jira_status
    
    return payload

