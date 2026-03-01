import json
import logging
from utils.llm_interface import LLMInterface
from utils.config import ROLE_PROMPTS
from langchain_core.prompts import PromptTemplate

class Editor:
    def __init__(self, llm: LLMInterface, tokens):
        self.llm = llm
        self.tokens = tokens

        # Define a reusable prompt template (chapter-style)
        self.prompt_template = PromptTemplate.from_template(
            "You are the Section Author.\n"
            "Your task is to write a single **chapter draft** for a larger professional research report.\n"
            "\n"
            "Section Title: {title}\n\n"
            "Evidence snippets:\n{sources}\n\n"
            "Previous draft:\n{prev_draft}\n\n"
            "Audit feedback:\n{prev_audit}\n\n"
            "Critical questions:\n{prev_critical}\n\n"
            "Guidelines:\n"
            "- Begin with a heading: '## {title}'\n"
            "- Write 2–3 subsections of content under this heading\n"
            "- Use clear, explanatory language that a non‑specialist reader can understand\n"
            "- Provide context and definitions for technical terms; avoid jargon unless explained\n"
            "- Use professional tone suitable for board‑level or strategic reports, but keep it accessible\n"
            "- Do NOT include:\n"
            "  * Executive summaries\n"
            "  * Table of contents\n"
            "  * References section\n"
            "  * Global conclusions\n"
            "- Focus only on the assigned section. Assume other sections will cover different aspects\n"
            "- Keep formatting consistent: Markdown headings, bullet points, tables where appropriate\n"
            "- Ensure the draft can be joined seamlessly with other chapters\n"
            "- Address issues flagged in the audit feedback\n"
            "- Incorporate answers or expansions suggested by critical questions\n"
            "- Use evidence snippets to strengthen arguments, but synthesize them into a narrative\n"
            "- Avoid repeating text verbatim; explain and contextualize instead\n"
            "- Please keep it clear, professional, and accessible."
        )

    def draft_section(self, section, sources, language_hint,
                      prev_draft="", prev_audit="", prev_critical="", max_tokens=None):
        """
        Refine or draft a section using evidence and previous round artifacts.
        Returns: Markdown draft string
        """
        sec_title = section.get("title", "Untitled Section")
        logging.info(f"[Editor] Drafting/refining section: {sec_title}")

        # Fill the template with values
        prompt = self.prompt_template.format(
            title=sec_title,
            sources=sources,
            prev_draft=prev_draft,
            prev_audit=prev_audit,
            prev_critical=prev_critical,
            language_hint=language_hint
        )

        try:
            draft = self.llm.query(prompt, role="editor", max_tokens=max_tokens)
        except Exception as e:
            logging.error(f"[Editor] LLM query failed: {e}")
            draft = f"## {sec_title}\n\n[Editor failed to generate draft]"

        return draft.strip()