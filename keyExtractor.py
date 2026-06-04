import os
import json
from google import genai
from google.genai import types
from config import Config

client = genai.Client(api_key=Config.GEMINI_API_KEY)

# ── System Prompt ──────────────────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """
You are a legal analyst assistant specializing in Indian law including BNS 
(Bharatiya Nyaya Sanhita), BNSS, IPC, and related statutes.

Your job is to extract structured legal information from a raw case description 
provided by an Indian lawyer.

Extract the following and return ONLY a valid JSON object, no explanation, 
no markdown, no backticks:

{
  "sections": [
    {
      "code": "BNS 103",
      "description": "Murder",
      "old_ipc_equivalent": "IPC 302"
    }
  ],
  "case_type": "Criminal / Civil / Family / Property / etc",
  "sub_type": "Murder / Bail / Divorce / Cheque Bounce / etc",
  "accused_position": "Accused / Complainant / Petitioner / Respondent",
  "key_facts": [
    "Client was arrested on 15 March 2024",
    "FIR filed by complainant",
    "Client claims self defence"
  ],
  "legal_issues": [
    "Whether act qualifies as self defence under BNS 34",
    "Whether FIR was filed with mala fide intent"
  ],
  "suggested_kanoon_queries": [
    "BNS 103 self defence acquittal High Court",
    "private defence murder Supreme Court landmark",
    "IPC 302 self defence Section 96 acquittal"
  ],
  "suggested_arguments": [
    "Right of private defence under BNS 34",
    "No premeditation — incident was spontaneous"
  ],
  "court_level": "Sessions Court / High Court / Supreme Court / District Court",
  "urgency": "Bail / Regular Hearing / Appeal / Anticipatory Bail / FIR Quash",
  "ai_summary": "A concise Markdown-formatted summary (under 500 words) of the case facts. Use bold headers (e.g., **Key Parties**, **Incident Details**, **Legal Sections**, **Location & Dates**) and bulleted lists to organize the information clearly. It must capture all key details as if briefing a senior advocate."
}

Rules:
- If a field cannot be determined from the description, return an empty array [] or empty string ""
- Always suggest 3 Indian Kanoon search queries optimized for finding relevant judgments
- Map old IPC sections to BNS equivalents wherever possible
- key_facts should be crisp bullet-style facts, not full sentences
- suggested_arguments should be legally sound, not generic
- ai_summary must be in Markdown format using bold headers and lists for readability, and strictly under 500 words.
- Return ONLY the JSON. Nothing else.
"""

# ── Extraction Function ────────────────────────────────────────────────────────

def extract_case_entities(case_description: str) -> dict:
    """
    Takes raw case description from lawyer.
    Returns structured JSON with sections, queries, arguments etc.
    """

    response = client.models.generate_content(
        model=Config.GEMINI_MODEL_NAME,
        contents=case_description,
        config=types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            temperature=0.1       # Low temp for consistent structured output
        )
    )

    raw = response.text.strip()

    # Clean up if Gemini wraps in markdown despite instructions
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        result = {
            "error": f"Failed to parse Gemini response: {str(e)}",
            "raw_response": raw,
            "sections": [],
            "case_type": "",
            "sub_type": "",
            "accused_position": "",
            "key_facts": [],
            "legal_issues": [],
            "suggested_kanoon_queries": [],
            "suggested_arguments": [],
            "court_level": "",
            "urgency": ""
        }

    return result


# ── Quick Test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_description = """
    My client Ramesh Sharma was arrested under BNS 103 for murder. 
    The FIR was filed by the deceased's brother claiming my client 
    intentionally killed the deceased during a land dispute in Indore 
    on 15th March 2024. My client claims he acted in self defence as 
    the deceased attacked him first with a weapon. We need bail 
    urgently from Sessions Court. Client has no prior criminal record.
    """

    result = extract_case_entities(test_description)
    print(json.dumps(result, indent=2))