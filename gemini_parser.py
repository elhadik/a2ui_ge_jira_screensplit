import os
import json
import io
from google import genai
from PIL import Image

def analyze_receipt_with_gemini(file_path: str = None, data_bytes: bytes = None, document_ai_result: dict = None, mime_type: str = None) -> dict:
    """
    Analyzes a receipt image and audits results using Gemini (via Vertex AI) from either file_path or in-memory data_bytes.
    Returns a confidence score out of 3.
    """
    # Load document media from bytes or file path using Part.from_bytes
    from google.genai import types
    document_media = None
    if data_bytes:
        document_media = types.Part.from_bytes(data=data_bytes, mime_type=mime_type)
    elif file_path:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image not found at {file_path}")
        with open(file_path, "rb") as f:
             document_media = types.Part.from_bytes(data=f.read(), mime_type=mime_type)
    else:
        raise ValueError("Must provide either file_path or data_bytes.")

    try:
        # Initialize client
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
        location = "us-central1" # Explicitly use us-central1 for Vertex AI Gemini
        model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
        
        if not project:
            raise ValueError("Missing GOOGLE_CLOUD_PROJECT environment variable.")

        # Initialize client with Vertex AI
        client = genai.Client(vertexai=True, project=project, location=location)

        prompt = f"""
        You are an expert receipt auditor. Your task is to audit the results extracted by an automated Document AI system from a receipt image and compare them are the actual text and content on the image.

        Analyze the attached image of a receipt and the provided Document AI extraction results (JSON).

        Document AI Extraction Results:
        {json.dumps(document_ai_result, indent=2) if document_ai_result else "None"}

        1. Compare the Document AI results with what you actually see on the image.
        2. Verify if the extracted values (Merchant, Date, Total, Tax) are correct and complete.
        3. Identify any discrepancies, omissions, or errors in the Document AI results.
        4. Issue a confidence score out of 3 based on your comparison, using the following criteria:
           - 3 (Excellent/Matched): The Document AI results perfectly match what is visible on the image. All key fields (Merchant, Date, Total, Tax) are correct, distinct, and unambiguous in both the JSON and the image. There are no discrepancies or omissions.
           - 2 (Fair/Partial Match): The Document AI results mostly match the image, but there are minor discrepancies, omissions, or ambiguities. For example, a minor date typo, a missed tax amount that is visible, or partially correct line items. The extraction is mostly usable but requires minor human correction.
           - 1 (Poor/Mismatch): Significant discrepancies exist between the Document AI results and the image. Key fields are missing, incorrect, or mismatched. The extraction failed significantly or is unusable.

        Output your response as a valid JSON object with the following structure:
        {{
          "confidence_score": integer (1-3),
          "criteria_met": "Detailed explanation of your audit. Specify which Document AI values matched the image, which were incorrect or missing, and how these findings justify the assigned score. Do not just repeat the criteria; provide specific examples from the image and JSON.",
          "extracted_values": {{
            "Merchant": "string or null",
            "Date": "string (MM/DD/YY or similar) or null",
            "Total": "string (number) or null",
            "Tax": "string (number) or null"
          }}
        }}

        Return ONLY the JSON object. Do not include any markdown formatting like ```json.
        """

        response = client.models.generate_content(
            model=model_name,
            contents=[prompt, document_media],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        # Verify JSON
        try:
            data = json.loads(response.text)
            return data
        except json.JSONDecodeError:
            # Fallback if JSON is not valid but looks like JSON
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)

    except Exception as e:
        print(f"Error during Gemini analysis: {e}")
        return {
            "confidence_score": 0,
            "error": str(e),
            "criteria_met": "Error during analysis."
        }
