import json
import logging
import re
from utils.llm_interface import LLMInterface

# --- Domain scaffolds ---
DOMAIN_SCAFFOLDS = {
    "Advanced Science & Technology": [
        "Introduction & Scope",
        "Scientific Foundations",
        "Current Innovations",
        "Methodologies & Tools",
        "Case Studies",
        "Challenges & Limitations",
        "Future Directions",
        "Conclusion"
    ],
    "Business & Economics": [
        "Introduction & Scope",
        "Market Overview",
        "Economic Theories & Models",
        "Case Studies",
        "Key Challenges",
        "Solutions & Strategies",
        "Future Trends",
        "Conclusion"
    ],
    "History & Literature": [
        "Introduction & Scope",
        "Historical Background",
        "Literary Analysis",
        "Key Figures & Movements",
        "Case Studies",
        "Critical Perspectives",
        "Future Research Directions",
        "Conclusion"
    ],
    "Entertainment & Media": [
        "Introduction & Scope",
        "Historical Context",
        "Current Media Landscape",
        "Case Studies",
        "Audience & Cultural Impact",
        "Challenges & Opportunities",
        "Future Trends",
        "Conclusion"
    ],
    "Interdisciplinary Topics": [
        "Introduction & Scope",
        "Cross‑Domain Background",
        "Methodologies",
        "Case Studies",
        "Challenges & Trade‑offs",
        "Future Opportunities",
        "Conclusion"
    ],
    "General": [
        "Introduction & Scope",
        "Historical Context",
        "Current Landscape",
        "Key Challenges",
        "Methodologies",
        "Case Studies",
        "Solutions",
        "Future Trends",
        "Conclusion"
    ]
}

# --- Domain classification prompt ---
DOMAIN_PROMPT = """
You are a domain classifier for research report planning.

Given the user query, classify it into ONE of the following domains:
- Advanced Science & Technology
- Business & Economics
- History & Literature
- Entertainment & Media
- Interdisciplinary Topics
- General

Return STRICT JSON only, with no explanation:
{{ "domain": "<one of the above>" }}

User query:
{query}
"""


class Planner:
    def __init__(self, llm: LLMInterface, tokens):
        self.llm = llm
        self.tokens = tokens

    def detect_domain(self, user_query: str, max_tokens=None) -> str:
        prompt = DOMAIN_PROMPT.format(query=user_query)
        raw = self.llm.query(prompt, role="planner", max_tokens=max_tokens)

        try:
            parsed = json.loads(raw)
            return parsed.get("domain", "General")
        except Exception:
            # fallback: regex search
            for domain in DOMAIN_SCAFFOLDS.keys():
                if domain.lower() in raw.lower():
                    return domain
            logging.warning("[Planner] Domain classification failed, defaulting to General")
            return "General"

    def plan(self, user_query: str, max_tokens=None, force_hardcode=True):
        """
        Generate a multi-section plan.
        - If force_hardcode=True: use domain-aware scaffold, refined by LLM.
        - Else: fall back to original LLM-driven parsing.
        """
        if force_hardcode:
            logging.info("[Planner] Using domain-aware scaffold with LLM refinement.")
            return self._refined_sections(user_query, max_tokens)

        # fallback to original parsing if needed
        prompt = f"User query: {user_query}\n\nGenerate structured sections."
        raw_reply = self.llm.query(prompt, role="planner", max_tokens=max_tokens)
        plan = self._parse_sections(raw_reply)

        if len(plan.get("sections", [])) < 5:
            logging.warning("[Planner] LLM produced too few sections, regenerating with scaffold.")
            return self._refined_sections(user_query, max_tokens)

        return plan

    def _refined_sections(self, user_query: str, max_tokens=None):
        """
        Start with domain-specific scaffold, then ask LLM to refine each section.
        Ensures minimum coverage even if LLM is weak.
        """
        domain = self.detect_domain(user_query, max_tokens)
        base_steps = DOMAIN_SCAFFOLDS.get(domain, DOMAIN_SCAFFOLDS["General"])

        prompt = (
            "We are designing a research report plan.\n"
            f"Domain: {domain}\n"
            "Refer to base_steps and the user_query.\n"
            "The first must be 'Introduction & Scope' and the last must be 'Conclusion'.\n"
            "Generate 7–9 meaningful section titles that cover the topic comprehensively.\n"
            "Return title line by line ONLY.\n\n"
            f"base_steps:\n{json.dumps(base_steps, ensure_ascii=False, indent=2)}\n\n"
            f"user_query:\n{user_query}\n"
        )

        plan_steps_str = self.llm.query(prompt, role="planner", max_tokens=max_tokens)
        plan_steps = [line.strip() for line in plan_steps_str.splitlines() if line.strip()]

        if len(plan_steps) < 5:
            logging.warning("[Planner] Plan too short, falling back to base_steps.")
            plan_steps = base_steps

        refined = []
        for i, title in enumerate(plan_steps, start=1):
            if title.lower().startswith("step"):
                title = base_steps[i-1] if i-1 < len(base_steps) else f"Section {i}"

            prompt = (
                f"You are the Planner.\n\n"
                f"Section: {title}\n"
                "Write a refined section plan that:\n"
                "- Explains clearly how this section relates to the overall query\n"
                "- Provides a concise narrative statement (1 sentence)\n"
                "- Suggests 2–3 subtopics or angles to cover\n"
                "- Defines 2–3 concrete deliverables for this section\n"
                "- Adds 1–2 critical questions for later refinement\n\n"
                "Return JSON in the following format:\n"
                "{\n"
                f"  \"id\": \"sec-{i}\",\n"
                "  \"title\": \"...\",\n"
                "  \"statement\": \"...\",\n"
                "  \"query\": \"...\",\n"
                "  \"deliverables\": [\"...\", \"...\"],\n"
                "  \"critical\": [\"...\", \"...\"]\n"
                "}\n\n"
                f"The query: {user_query}"
            )
            try:
                reply = self.llm.query(prompt, role="planner", max_tokens=max_tokens)
                parsed = json.loads(reply)
                refined.append(parsed)
            except Exception:
                refined.append({
                    "id": f"sec-{i}",
                    "title": title,
                    "statement": f"This section will discuss {title} in relation to {user_query}.",
                    "query": user_query,
                    "deliverables": [],
                    "critical": []
                })

        return {"sections": refined}

    def _parse_sections(self, text: str):
        sections = []
        for match in re.finditer(r"##\s*(sec-\d+):?\s*(.+)", text):
            sec_id, title = match.groups()
            sections.append({"id": sec_id.strip(), "title": title.strip(), "content": text})
        return {"sections": sections}