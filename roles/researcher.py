import logging, json, uuid, requests
from utils.helpers import file_hash
from utils.config import ROLE_PROMPTS

class Researcher:
    def __init__(self, search_engine, project_id, llm, limit=10):
        self.search_engine = search_engine   # must expose .search(query, limit=...)
        self.project_id = project_id
        self.llm = llm
        self.limit = limit

    def deep_search(self, section, user_query, prev_audit="", prev_critical="", max_tokens=256):
        title = section.get("title", section.get("id", ""))
        logging.info(f"[Researcher] Deep search for section: {title}")

        # Refine queries with LLM
        prompt = f"""
You are the Researcher. Generate 2–3 focused search queries for deeper evidence collection.

Section title: {title}
User query: {user_query}
Audit feedback: {prev_audit}
Critical questions: {prev_critical}

Return STRICT JSON only:
{{ "queries": ["query1", "query2", "query3"] }}
"""
        raw = self.llm.query(prompt, role="researcher", max_tokens=max_tokens)
        try:
            parsed = json.loads(raw)
            queries = parsed.get("queries", [])
        except Exception as e:
            logging.warning(f"[Researcher] Query refinement failed: {e}")
            queries = [f"{user_query} {title}"]

        evidence = []
        seen_hashes = set()

        for q in queries:
            try:
                results = self.search_engine.search(q, limit=self.limit)
            except Exception as e:
                logging.error(f"[Researcher] Search failed for {q}: {e}")
                continue

            results = self._filter_results_with_llm(q, results, max_tokens=max_tokens)

            for r in results:
                url = r.get("url", "")
                snippet = r.get("snippet", "")

                if url:
                    try:
                        resp = requests.get(url, timeout=30)
                        text = resp.text[:2000]
                        r["snippet"] = text
                    except Exception as e:
                        logging.warning(f"[Researcher] Deep fetch failed: {url} :: {e}")
                        continue # skip inaccessible pages
                
                if not r.get("snippet"):
                    continue

                try:
                    compressed = self.llm.query(
                        f"{ROLE_PROMPTS['planner']}\nSummarize evidence:\n{r['snippet']}",
                        role="researcher",
                        max_tokens=512
                    )
                    r["compressed"] = compressed.strip()
                except Exception as e:
                    r["compressed"] = r["snippet"][:1000]
                    logging.warning(f"[Researcher] Compression failed: {e}")

                r["source_id"] = str(uuid.uuid4())
                r["hash"] = file_hash(r["compressed"])
                r["origin"] = "researcher-deep"
                r["depth"] = "deep"

                if r["hash"] not in seen_hashes:
                    evidence.append(r)
                    seen_hashes.add(r["hash"])

        logging.info(f"[Researcher] Deep search produced {len(evidence)} evidence items")
        return evidence

    def _filter_results_with_llm(self, query, results, max_tokens=256):
        """Use LLM to decide if each search result is relevant to the query."""
        filtered = []
        for r in results:
            prompt = f"""
You are a relevance filter for search results.

User query: {query}

Candidate result:
Title: {r.get('title','')}
Snippet: {r.get('snippet','')}
URL: {r.get('url','')}

Decide if this result is directly useful for answering the query.
Return STRICT JSON only:
{{ "relevant": true/false, "reason": "short explanation" }}
"""
            raw = self.llm.query(prompt, role="collector", max_tokens=max_tokens)
            try:
                parsed = json.loads(raw)
                if parsed.get("relevant", False):
                    r["filter_reason"] = parsed.get("reason", "")
                    filtered.append(r)
            except Exception:
                # fallback heuristic
                if any(w.lower() in (r.get("snippet","")+r.get("title","")).lower() for w in query.split()):
                    r["filter_reason"] = "Fallback keyword match"
                    filtered.append(r)
        return filtered