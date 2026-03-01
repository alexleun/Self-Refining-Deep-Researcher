import json
import logging
from utils.llm_interface import LLMInterface
from utils.config import ROLE_PROMPTS

class Supervisor:
    def __init__(self, llm: LLMInterface, tokens, max_tokens=None):
        self.llm = llm
        self.tokens = tokens
        self.max_tokens = max_tokens

    def score(self, draft: str, max_tokens=None) -> dict:
        prompt = ROLE_PROMPTS['supervisor'] + draft
        raw = self.llm.query(prompt, role="supervisor", max_tokens=max_tokens or self.max_tokens)

        try:
            result = json.loads(raw)
            # ✅ If rewrite is provided, override draft
            if "rewrite" in result and result["rewrite"]:
                result["final_answer"] = result["rewrite"]
            else:
                result["final_answer"] = draft
            return result
        except Exception as e:
            logging.error(f"[Supervisor] Failed to parse JSON: {e}")
            return {
                "accuracy": 0, "coherence": 0, "completeness": 0,
                "creativity": 0, "format": 0, "overall": 0.0,
                "strengths": [], "weaknesses": [], "improvements": [],
                "final_answer": draft
            }