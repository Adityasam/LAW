import os
import time
from pathlib import Path
from google import genai
from google.genai import types
from config import Config

client = genai.Client(api_key=Config.GEMINI_API_KEY)

def process_document(file_path: str):
    """
    Sends a file (PDF or Image) to Gemini to extract text and generate a summary.
    Returns (extracted_text, summary).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # 1. Upload the file to Gemini
    print(f"Uploading {path.name} to Gemini...")
    uploaded_file = client.files.upload(file=str(path))
    
    # Wait for the file to be processed by Gemini (especially for large PDFs)
    while uploaded_file.state.name == "PROCESSING":
        print(".", end="", flush=True)
        time.sleep(2)
        uploaded_file = client.files.get(name=uploaded_file.name)

    if uploaded_file.state.name == "FAILED":
        raise Exception(f"Gemini file processing failed: {uploaded_file.name}")

    print(f"\nFile {path.name} is ready. Extracting info...")

    # 2. Ask Gemini to extract text and summarize
    # We use a prompt that asks for both in a structured way.
    prompt = """
    Analyze the attached document carefully.
    1. Extract all readable text from the document verbatim.
    2. Provide a professional legal summary of the document (around 200-300 words). 
       
    Use Markdown formatting for the summary:
    - Use bold headings for sections like **Nature of Document**, **Key Parties**, **Critical Dates**, **Core Allegations/Facts**, and **Legal Implications**.
    - Use bullet points for lists.
    - Ensure it is structured for easy reading in a legal workspace.
    
    Format your response exactly as:
    ---TEXT START---
    [Verbatim Text Here]
    ---TEXT END---
    ---SUMMARY START---
    [Markdown-formatted Summary Here]
    ---SUMMARY END---
    """

    response = client.models.generate_content(
        model=Config.GEMINI_MODEL_NAME,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type),
                    types.Part.from_text(text=prompt)
                ]
            )
        ]
    )

    full_response = response.text
    
    # 3. Parse the response
    extracted_text = ""
    summary = ""
    
    try:
        if "---TEXT START---" in full_response and "---TEXT END---" in full_response:
            extracted_text = full_response.split("---TEXT START---")[1].split("---TEXT END---")[0].strip()
        
        if "---SUMMARY START---" in full_response and "---SUMMARY END---" in full_response:
            summary = full_response.split("---SUMMARY START---")[1].split("---SUMMARY END---")[0].strip()
        else:
            # Fallback if parsing fails
            summary = full_response[:1000] # Just a chunk
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        extracted_text = full_response
        summary = "Error parsing summary."

    # Clean up the file from Gemini storage (optional but good practice)
    try:
        client.files.delete(name=uploaded_file.name)
    except:
        pass

    return extracted_text, summary
