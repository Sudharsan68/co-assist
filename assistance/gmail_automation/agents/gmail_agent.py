import json
import re
from typing import Any, Dict, List, Optional
from groq import Groq

JSON_EXAMPLE = {
    "to": ["recipient@example.com"],
    "cc": [],
    "bcc": [],
    "subject": "Meeting Tomorrow at 2 PM",
    "body": "Hi <name>,\n\nLet's meet tomorrow at 2 PM in the 3F conference room.\n\nBest,\nSudharsan",
    "tone": "neutral",
    "draft": False,
}

SYSTEM_RULES = (
    "You are an expert email writing assistant.\n"
    "- Always output STRICT JSON, no code block fences.\n"
    "- Keys: to[list of strings], cc[list], bcc[list], subject[string], body[string], tone[string], draft[bool].\n"
    "- Never include placeholders like 'TBD' if the user already gave details.\n"
    "- If the user doesn't state recipients, infer from context if safe (e.g., 'my manager' -> manager@example.com) ONLY if the domain is provided; otherwise leave an EMPTY LIST for 'to'.\n"
    "- Create a concise, informative SUBJECT from the request.\n"
    "- Create a clear, well-structured BODY with salutation and sign-off when appropriate.\n"
    "- Use the requested tone if specified (e.g., formal, friendly, assertive). Default tone is neutral.\n"
    "- Keep line length readable; use newlines between paragraphs.\n"
)

class GmailAgent:
    def __init__(self, groq_api_key: str, model: str = "llama-3.1-8b-instant"):
        self.client = Groq(api_key=groq_api_key)
        self.model = model

    def _extract_json(self, text: str) -> str:
        """Extract the first JSON object from arbitrary text.
        Groq usually respects the instruction, but this is a safe-guard.
        """
        # If it is already pure JSON, just return
        txt = text.strip()
        if txt.startswith("{") and txt.endswith("}"):
            return txt
        # find the first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("Model did not return JSON.")
        return m.group(0)

    def parse_task(self, task: str, tone_hint: Optional[str] = None) -> Dict[str, Any]:
        """Turn a natural language request into structured email instructions.
        Returns a Python dict with keys: to, cc, bcc, subject, body, tone, draft
        """
        user_block = (
            f"Task: {task}\n" + (f"Tone hint: {tone_hint}\n" if tone_hint else "") +
            "Return ONLY a JSON object with the exact keys described."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_RULES},
                    {"role": "user", "content": user_block},
                ],
                temperature=0.2,
                max_tokens=600,
            )
            raw = resp.choices[0].message.content
            json_str = self._extract_json(raw)
            data = json.loads(json_str)

            # Post-validate and normalize
            data.setdefault("to", [])
            data.setdefault("cc", [])
            data.setdefault("bcc", [])
            data.setdefault("tone", "neutral")
            data.setdefault("draft", False)

            # Coerce scalar 'to' into list
            if isinstance(data.get("to"), str):
                data["to"] = [data["to"]]

            # Basic checks
            if not isinstance(data.get("subject", ""), str) or not data["subject"].strip():
                raise ValueError("Missing subject from model output.")
            if not isinstance(data.get("body", ""), str) or not data["body"].strip():
                raise ValueError("Missing body from model output.")
            for k in ("to", "cc", "bcc"):
                if not isinstance(data[k], list):
                    raise ValueError(f"'{k}' must be a list of strings")
                # Make sure all are strings
                data[k] = [str(v).strip() for v in data[k] if str(v).strip()]

            return data
        except Exception as e:
            raise ValueError(f"Failed to parse task: {e}")