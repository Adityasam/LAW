import os
import requests
import json
from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyDMNV7CW-JmuSf8EV3X9rR4-D0k04V3Mfo")
KANOON_API_KEY = "570ff9983179b8b259f19cfbb7c9b32dc9ff44d4"

SYSTEM_PROMPT = """
You are an expert Indian legal assistant with deep knowledge of BNS, BNSS, BSA, IPC, CrPC, and Indian case law.

A lawyer will provide you with:
1. Case facts and description
2. Relevant sections (BNS/IPC)
3. Judgments retrieved from Indian Kanoon

Your job is to analyze everything and give the lawyer a clear, structured legal opinion.

RESPONSE FORMAT — always respond in this exact structure:

**LEGAL POSITION**
One paragraph summary of where the accused/client stands legally based on the facts and applicable sections.

**RELEVANT SECTIONS**
List each section with its exact legal implication for this specific case. Do not copy the section text — explain how it applies here.

**KEY ARGUMENTS TO USE**
Numbered list of strongest legal arguments the lawyer can make. Be specific, not generic.

**PRECEDENTS TO CITE**
For each judgment provided, state:
- Judgment name and court
- What it established
- How it directly helps this case
Only include judgments that genuinely support the case. Do not force irrelevant precedents.

**WEAK POINTS / RISKS**
Honest assessment of the weak points in the case the opposing side may exploit. Lawyer needs to know this.

**RECOMMENDED NEXT STEPS**
Concrete procedural steps — what to file, what to argue, what to request from the court.

STRICT RULES:
- Never invent judgments or section numbers. Use only what is provided.
- If a provided judgment does not help the case, say so clearly instead of misrepresenting it.
- If the provided context is insufficient to give a confident opinion, say what additional information is needed.
- Always cite the judgment name when referencing it.
- Write in clear professional English. Avoid vague legal filler language.
- Never give a disclaimer like "consult a lawyer" — you are assisting the lawyer directly.
"""

RAG_SYSTEM_PROMPT = """
You are a senior Indian criminal defense lawyer with 25 years of experience 
in Sessions Courts, High Courts, and Supreme Court of India.

You have deep expertise in:
- BNS, BNSS, BSA and their IPC/CrPC equivalents
- Bail jurisprudence in Indian courts
- Cross examination strategy
- Drafting arguments, applications, and written submissions
- Reading and exploiting weaknesses in prosecution cases

You are currently assisting a junior lawyer who has shared a case with you.
You must respond exactly as a senior advocate would brief a junior — specific, 
tactical, no fluff.

ANSWER STYLE:
- Language - Hindi
- Script - Devanagari
- Never give textbook definitions — the lawyer knows the law
- Always give tactical advice — what to argue, how to argue, what to watch for
- When asked about hearing preparation, give a specific game plan for THIS case
- Point out what the prosecution WILL argue and how to counter it
- If facts are weak, say so honestly and suggest how to handle it
- Use Indian legal terminology naturally (vakalatnama, remand, anticipatory bail, 
  chargesheet, committal, etc.)
- Short sharp sentences. No lengthy explanations unless asked.

STRICT CONSTRAINTS:
- Base every answer on the case context provided — not generic law
- If you reference a judgment, it must come from the provided Kanoon data
- Never invent facts about the case
- If the case context is insufficient to answer properly, ask for the 
  specific missing detail
- Do not repeat case facts back to the lawyer — they know their case

HEARING PREPARATION FORMAT (Only when asked or necessary):
When asked to prepare for a hearing, always structure as:
1. Our strongest point — lead with this
2. Expected prosecution argument — and exact counter
3. Sections and judgments to cite — with one line on why each helps
4. What to watch for from the judge — bail matters vs regular hearing tone differs
5. Documents to have ready
6. What NOT to argue — points that will hurt more than help
"""


# ── Step 1: Fetch judgments from Indian Kanoon ─────────────────────────────────

def fetch_kanoon_results(queries: list[str], results_per_query: int = 3) -> list[dict]:
    """
    Takes list of search queries from extractor output.
    Returns list of judgment dicts with title + snippet.
    """
    headers = {"Authorization": f"Token {KANOON_API_KEY}"}
    judgments = []
    seen_ids = set()

    for query in queries:
        try:
            response = requests.post(
                "https://api.indiankanoon.org/search/",
                data={"formInput": query, "pagenum": 0},
                headers=headers,
                timeout=10
            )
            data = response.json()
            docs = data.get("docs", [])[:results_per_query]

            for doc in docs:
                doc_id = doc.get("tid")
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    judgments.append({
                        "title": doc.get("title", "Unknown"),
                        "court": doc.get("docsource", "Unknown Court"),
                        "date": doc.get("publishdate", ""),
                        "snippet": doc.get("headline", ""),   # Short preview
                        "url": f"https://indiankanoon.org/doc/{doc_id}/",
                        "doc_id": doc_id
                    })
        except Exception as e:
            print(f"Kanoon query failed for '{query}': {e}")
            continue

    return judgments


# ── Step 2: Build the user message ────────────────────────────────────────────

def build_user_message(case_description: str, extracted: dict, judgments: list[dict]) -> str:
    """
    Combines case facts + sections + kanoon judgments into one prompt message.
    This is what gets passed to Gemini as the user content.
    """

    # Case facts block
    message = f"""
    CASE DESCRIPTION:
    {case_description}

    SECTIONS INVOLVED:
    """
    for s in extracted.get("sections", []):
        message += f"- {s['code']} ({s.get('old_ipc_equivalent', '')}) — {s['description']}\n"

    message += f"\nCASE TYPE: {extracted.get('case_type', '')} — {extracted.get('sub_type', '')}"
    message += f"\nCOURT LEVEL: {extracted.get('court_level', '')}"
    message += f"\nURGENCY: {extracted.get('urgency', '')}"

    # Key facts block
    message += "\n\nKEY FACTS:\n"
    for fact in extracted.get("key_facts", []):
        message += f"- {fact}\n"

    # Kanoon judgments block
    message += "\n\nRELEVANT JUDGMENTS FROM INDIAN KANOON:\n"
    if judgments:
        for i, j in enumerate(judgments, 1):
            message += f"""
            Judgment {i}:
            Title: {j['title']}
            Court: {j['court']}
            Date: {j['date']}
            Summary: {j['snippet']}
            Link: {j['url']}
            """
    else:
        message += "No judgments retrieved. Base your opinion on the sections and facts only.\n"

    message += "\nBased on all of the above, provide your legal analysis."

    return message


# ── Step 3: Get Gemini advice ──────────────────────────────────────────────────

def get_legal_advice(case_description: str, extracted: dict) -> dict:
    """
    Main function to call from Flask route.
    Pass case_description and extracted entities from extractor.py.
    Returns judgment links (no Gemini advice yet).
    """

    # Fetch Kanoon data using queries from extractor
    queries = extracted.get("suggested_kanoon_queries", [])
    judgments = fetch_kanoon_results(queries)

    print(f"Retrieved {len(judgments)} judgments for queries: {queries}")

    return {
        "advice": "", # No Gemini advice yet
        "judgments": judgments      # Return these so UI can show clickable links
    }

def stream_legal_chat(user_message: str, relevant_chunks: list[dict], history: list[dict] = None, case_facts: str = None):
    """
    Streams a response from Gemini using RAG chunks, chat history, and case facts.
    """
    context_parts = []
    for i, item in enumerate(relevant_chunks):
        m = item.get("metadata", {})
        header = f"Snippet {i+1} [Source: {m.get('title', 'Unknown')} | {m.get('court', '')} | {m.get('date', '')}]"
        context_parts.append(f"{header}\n{item['text']}")
    
    context = "\n\n".join(context_parts)
    
    contents = []
    if history:
        for msg in history:
            role = "user" if msg["role"] == "lawyer" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
            
    # Add current prompt with context and case facts
    facts_context = f"CURRENT CASE FACTS:\n{case_facts}\n\n" if case_facts else ""
    full_prompt = f"{facts_context}CONTEXT FROM JUDGMENTS:\n{context}\n\nUSER QUESTION: {user_message}"
    contents.append(types.Content(role="user", parts=[types.Part(text=full_prompt)]))

    response = client.models.generate_content_stream(
        model="models/gemini-3.1-flash-lite-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=RAG_SYSTEM_PROMPT,
            temperature=0.3
        )
    )
    
    for chunk in response:
        if chunk.text:
            yield chunk.text

def fetch_doc_by_id(doc_id: str) -> dict:
    headers = {"Authorization": f"Token {KANOON_API_KEY}"}
    
    response = requests.post(
        f"https://api.indiankanoon.org/doc/{doc_id}/",
        headers=headers,
        timeout=10
    )
    return response.json()

# ── Quick Test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulate what extractor.py would return
    # mock_extracted = {
    #     "sections": [
    #         {"code": "BNS 103", "description": "Murder", "old_ipc_equivalent": "IPC 302"},
    #         {"code": "BNS 34", "description": "Right of private defence", "old_ipc_equivalent": "IPC 96"}
    #     ],
    #     "case_type": "Criminal",
    #     "sub_type": "Murder / Bail",
    #     "court_level": "Sessions Court",
    #     "urgency": "Bail",
    #     "key_facts": [
    #         "Client arrested on 15 March 2024",
    #         "FIR filed by deceased's brother",
    #         "Client claims self defence",
    #         "Deceased attacked first with weapon",
    #         "No prior criminal record"
    #     ],
    #     "suggested_kanoon_queries": [
    #         "BNS 103 self defence bail granted Sessions Court",
    #         "IPC 302 private defence acquittal Supreme Court",
    #         "murder self defence land dispute High Court"
    #     ]
    # }

    # case_desc = """
    # My client Ramesh Sharma was arrested under BNS 103 for murder. 
    # FIR filed by deceased's brother. Client claims self defence as 
    # deceased attacked first with a weapon during a land dispute in 
    # Indore on 15th March 2024. Need bail from Sessions Court urgently.
    # """

    # result = get_legal_advice(case_desc, mock_extracted)

    # print("=== LEGAL ADVICE ===")
    # print(result["advice"])
    # print("\n=== JUDGMENT LINKS ===")
    # for j in result["judgments"]:
    #     print(f"- {j['title']} → {j['url']}")

    docid = 130575686
    doc = fetch_doc_by_id(docid)
    print(doc)