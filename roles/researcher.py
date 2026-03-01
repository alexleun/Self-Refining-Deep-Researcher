import os, uuid, logging, requests
from utils.helpers import safe_name, file_hash
from utils.config import ROLE_PROMPTS

class Researcher:
    """
    Researcher role: performs deeper, targeted searches for each section.
    Cooperates with Editor, Auditor, Specialist by enriching evidence pool.
    """

    def __init__(self, search_engine, project_id, llm, limit=10):
        self.search_engine = search_engine   # usually Collector.search_engine (SearXNG client)
        self.project_id = project_id
        self.llm = llm                       # LLMInterface for query refinement
        self.limit = limit

    def refine_query(self, section, user_query, prev_audit="", prev_critical=""):
        """
        Use LLM to refine search query based on section title, user query,
        and feedback from previous audit/critical questions.
        """
        base = section.get("title", section.get("id", ""))
        prompt = (
            f"{ROLE_PROMPTS['researcher']}\n"
            f"User query: {user_query}\n"
            f"Section: {base}\n"
            f"Audit feedback: {prev_audit}\n"
            f"Critical questions: {prev_critical}\n\n"
            f"Generate 2–3 focused search queries for deeper evidence."
        )
        try:
            refined = self.llm.query(prompt, role="researcher", max_tokens=256)
            queries = [q.strip() for q in refined.split("\n") if q.strip()]
            return queries[:3]
        except Exception as e:
            logging.warning(f"[Researcher] Query refinement failed: {e}")
            return [f"{user_query} {base}"]

    def deep_search(self, section, user_query, prev_audit="", prev_critical=""):
        """
        Perform deep search for a section using refined queries.
        Returns enriched evidence items (dicts).
        """
        queries = self.refine_query(section, user_query, prev_audit, prev_critical)
        evidence = []

        for q in queries:
            try:
                results = self.search_engine.searx_search(q, limit=self.limit)
            except Exception as e:
                logging.error(f"[Researcher] Search failed for {q}: {e}")
                continue

            for r in results:
                url = r.get("url", "")
                snippet = r.get("snippet", "")

                # Attempt deep fetch
                if url:
                    try:
                        resp = requests.get(url, timeout=30)
                        text = resp.text[:2000]
                        r["snippet"] = text
                    except Exception as e:
                        logging.warning(f"[Researcher] Deep fetch failed: {url} :: {e}")

                # Compress snippet
                try:
                    compressed = self.llm.query(
                        f"{ROLE_PROMPTS['planner']}\nSummarize evidence:\n{snippet}",
                        role="researcher",
                        max_tokens=512
                    )
                    r["compressed"] = compressed.strip()
                except Exception as e:
                    r["compressed"] = snippet[:1000]
                    logging.warning(f"[Researcher] Compression failed: {e}")

                r["source_id"] = str(uuid.uuid4())
                r["hash"] = file_hash(r["compressed"])
                r["origin"] = "researcher-deep"
                r["depth"] = "deep"
                evidence.append(r)

        return evidence