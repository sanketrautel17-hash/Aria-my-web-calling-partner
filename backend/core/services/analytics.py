"""
Aria — Post-call Analysis Service.

Uses Groq LLM to analyze a call transcript and determine
if the user was interested in a loan. Shared for both web
and phone calls (single Loan Assistant persona).
"""

import json
from groq import AsyncGroq
from core.config import settings
from commons.logger import logger

log = logger(__name__)

# ── Analysis Prompt ───────────────────────────────────────────────────────────
ANALYSIS_PROMPT_TEMPLATE = """
Analyze the following sales call transcript between an AI assistant and a user.
Determine if the user is interested in a loan.

Transcript: {transcript}

Return a valid JSON object with these fields:
- is_interested: boolean (true/false)
- loan_type: string (e.g., "Home", "Personal", "Auto", or "None")
- lead_score: integer (1-10, where 10 is highly interested)
- summary: string (brief summary of the conversation)
- next_step: string (what should happen next?)

Do not include any markdown formatting. Just the JSON string.
"""


async def analyze_call_transcript(transcript_data: list) -> dict:
    """
    Analyze a call transcript using Groq LLM.
    Works identically for web calls and phone calls.

    Returns a dict with keys: is_interested, loan_type, lead_score, summary, next_step
    """
    try:
        transcript_str = str(transcript_data)[:10000]  # Truncate if too long
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(transcript=transcript_str)

        client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        completion = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        text = completion.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]

        return json.loads(text)
    except Exception as e:
        log.error(f"Failed to analyze call transcript: {e}")
        return {"error": str(e), "is_interested": False}
