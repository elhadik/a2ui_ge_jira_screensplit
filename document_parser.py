import os
import json
import io
from google import genai
from google.genai import types
from PIL import Image

def parse_document(file_path: str = None, data_bytes: bytes = None, mime_type: str = "application/pdf") -> dict:
    """
    Parses a document using Gemini 2.5 by reading either file_path or in-memory data_bytes.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
    location = "us-central1"
    
    if not project_id:
        raise ValueError(
            "Missing Environment Variables. Please set GOOGLE_CLOUD_PROJECT before running."
        )

    # Initialize client with Vertex AI
    client = genai.Client(vertexai=True, project=project_id, location=location)

    # Load document media from bytes or file path using Part.from_bytes
    document_media = None
    if data_bytes:
        document_media = types.Part.from_bytes(data=data_bytes, mime_type=mime_type)
    elif file_path:
        with open(file_path, "rb") as f:
             document_media = types.Part.from_bytes(data=f.read(), mime_type=mime_type)
    else:
        raise ValueError("Must provide either file_path or data_bytes.")

    prompt = """
    You are an expert retail document parser acting as an OCR and data extraction system.
    Extract the text and structured data from the provided document.
    
    Output your response as a valid JSON object strictly matching this schema:
    {
      "document_type": "string (The type of document, e.g., 'Invoice', 'Receipt', 'Processed Document')",
      "entities": [
          {
             "type": "string (e.g., supplier_name, total_amount, invoice_date, etc.)",
             "mention_text": "string (the exact value extracted)"
          }
      ],
      "line_items": [
          {
             "description": "string (item description)",
             "quantity": "string (item quantity)",
             "unit_price": "string (item unit price)",
             "amount": "string (item total amount)"
          }
      ],
      "raw_text_summary": "string (a brief summary of the raw text or the first 500 characters found in the document)"
    }
    
    Return ONLY a single valid JSON object. Do not include markdown formatting like ```json.
    """

    model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, document_media],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Verify and load JSON
        try:
            parsed_data = json.loads(response.text)
        except json.JSONDecodeError:
            text = response.text.replace("```json", "").replace("```", "").strip()
            parsed_data = json.loads(text)
            
        # Ensure default structure if the model missed something
        parsed_data.setdefault("document_type", "Processed Document")
        parsed_data.setdefault("entities", [])
        parsed_data.setdefault("line_items", [])
        parsed_data.setdefault("raw_text_summary", "Summary unvailable.")

    except Exception as e:
        print(f"Error during Gemini parsing: {e}")
        parsed_data = {
            "document_type": "Processed Document",
            "entities": [],
            "line_items": [],
            "raw_text_summary": f"Error: {e}"
        }

    # Save the parsed data to a JSON file locally if file_path was provided
    if file_path:
        json_path = file_path + ".json"
        try:
            with open(json_path, 'w') as f:
                json.dump(parsed_data, f, indent=4)
            print(f"Saved parsed JSON to {json_path}")
        except Exception as e:
            print(f"Warning: Could not save json to file: {e}")

    return parsed_data
