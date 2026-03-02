# import json
# import logging
# from utils.llm_interface import LLMInterface
# from utils.config import ROLE_PROMPTS

# class Supervisor:
    # def __init__(self, llm: LLMInterface, tokens, max_tokens=None):
        # self.llm = llm
        # self.tokens = tokens
        # self.max_tokens = max_tokens

    # def score(self, draft: str, max_tokens=None) -> dict:
        # prompt = ROLE_PROMPTS['supervisor'] + draft
        # raw = self.llm.query(prompt, role="supervisor", max_tokens=max_tokens or self.max_tokens)

        # try:
            # result = json.loads(raw)
            # # ✅ If rewrite is provided, override draft
            # if "rewrite" in result and result["rewrite"]:
                # result["final_answer"] = result["rewrite"]
            # else:
                # result["final_answer"] = draft
            # return result
        # except Exception as e:
            # logging.error(f"[Supervisor] Failed to parse JSON: {e}")
            # return {
                # "accuracy": 0, "coherence": 0, "completeness": 0,
                # "creativity": 0, "format": 0, "overall": 0.0,
                # "strengths": [], "weaknesses": [], "improvements": [],
                # "final_answer": draft
            # }
            
import logging
import json

class Supervisor:
    def __init__(self, threshold=7.0, max_rounds=3):
        """
        Supervisor orchestrates evaluation rounds.
        - threshold: minimum avg_overall score required to finalize
        - max_rounds: maximum number of refinement rounds allowed
        """
        self.threshold = threshold
        self.max_rounds = max_rounds
        self.last_avg_score = None  # store last computed average score

    def parse_json_safe(self, raw_output, default_score=5):
        """
        Safely parse JSON from role output.
        Returns dict with 'score' and 'comments'.
        """
        if not raw_output or not raw_output.strip():
            logging.error("[Supervisor] Empty output, using default score")
            return {"score": default_score, "comments": "Empty output"}

        try:
            parsed = json.loads(raw_output)
            if "score" not in parsed:
                parsed["score"] = default_score
            if "comments" not in parsed:
                parsed["comments"] = "No comments"
            return parsed
        except Exception as e:
            logging.error(f"[Supervisor] Failed to parse JSON: {e}")
            return {"score": default_score, "comments": "Parse error"}

    def score(self, enriched_text, max_tokens=256):
        """
        Score a section draft using LLM.
        Returns dict with 'score' and 'comments'.
        """
        # Build scoring prompt
        prompt = f"""
You are the Supervisor. Evaluate the following section draft.

Draft:
{enriched_text}

Return STRICT JSON only:
{{ "score": <number between 1-10>, "comments": "<short explanation>" }}
"""
        try:
            raw_output = self.llm.query(prompt, role="supervisor", max_tokens=max_tokens)
        except Exception as e:
            logging.error(f"[Supervisor] LLM scoring failed: {e}")
            return {"score": 5, "comments": "LLM scoring failed"}

        return self.parse_json_safe(raw_output, default_score=5)

    def evaluate_round(self, section_results):
        """
        Compute average overall score from section results.
        Each section_result should be a dict with 'score'.
        """
        scores = [s.get("score", 5) for s in section_results if isinstance(s, dict)]
        avg = sum(scores) / len(scores) if scores else 5.0
        self.last_avg_score = avg
        logging.info(f"[Supervisor] Round evaluation avg_overall={avg:.2f}")
        return avg

    def decide_next_step(self, avg_overall, current_round):
        """
        Decide whether to run another round or finalize.
        """
        if avg_overall < self.threshold and current_round < self.max_rounds:
            logging.info(
                f"[Supervisor] avg_overall={avg_overall:.2f} below threshold {self.threshold}, "
                f"starting round {current_round+1}"
            )
            return "next_round"
        else:
            logging.info(
                f"[Integration] Using round {current_round} with avg_overall={avg_overall:.2f}"
            )
            return "finalize"