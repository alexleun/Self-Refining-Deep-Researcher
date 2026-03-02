import os, uuid, logging, requests, json
from utils.helpers import file_hash
from roles.llm_interface import LLMInterface
from utils.pdf_handler import fetch_and_split_pdf
from utils.config import ROLE_PROMPTS

class Collector:
    def __init__(self, search_engine, project_id, limit, llm: LLMInterface):
        self.search_engine = search_engine   # must expose .search(query, limit=...)
        self.project_id = project_id
        self.llm = llm
        self.limit = limit

    def compress_semantic(self, snippet: str, max_words: int, max_tokens=None) -> str:
        words = snippet.split()
        if len(words) <= max_words:
            return snippet
        prompt = (
            f"{ROLE_PROMPTS['planner']}\n"
            f"rewrite text <={max_words}\n"
            f"{snippet}"
        )
        return self.llm.query(prompt, role="collector", max_tokens=max_tokens).strip()

    def fetch_deep(self, url: str, max_chars: int = 4000) -> str:
        try:
            r = requests.get(url, timeout=60)
            return r.text[:max_chars]
        except Exception as e:
            logging.warning(f"Deep fetch failed: {url} :: {e}")
            return ""

    def ingest_local_files(self, root: str, patterns=(".md", ".txt")):
        docs = []
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if any(fn.lower().endswith(p) for p in patterns):
                    path = os.path.join(dirpath, fn)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                        docs.append({
                            "source_id": str(uuid.uuid4()),
                            "title": fn,
                            "url": path,
                            "snippet": text[:4000],
                            "date": "",
                            "engine": "local",
                            "origin": "local-file",
                        })
                    except Exception as e:
                        logging.warning(f"Failed to ingest local file: {path} :: {e}")
        return docs

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

    def collect(self, user_query: str, limit=15, deep_visit=True, local_dir=None,
                max_tokens=None, researcher=None, min_required=10):
        limit = min(self.limit, limit)
        results = self.search_engine.search(user_query, limit=limit)

        # 🔑 LLM relevance filter
        results = self._filter_results_with_llm(user_query, results, max_tokens=max_tokens)

        enriched = []
        seen_hashes = set()

        for r in results:
            url = r.get("url", "")
            snippet = r.get("snippet", "") or ""

            if "Error fetching" in snippet or snippet.strip() == "":
                continue

            if url and url.lower().endswith(".pdf"):
                pdf_chunks = fetch_and_split_pdf(url, self.project_id)
                enriched.extend(pdf_chunks)
                continue

            if deep_visit and url:
                text = self.fetch_deep(url)
                if text:
                    snippet = text[:1200]
                    r["snippet"] = snippet

            max_words = 1000 if len(snippet.split()) > 1200 else 800
            r["compressed"] = self.compress_semantic(snippet, max_words=max_words, max_tokens=max_tokens)
            r["hash"] = file_hash(r["compressed"])
            r["source_type"] = "html"

            if len(r["compressed"]) < 200 or r["hash"] in seen_hashes:
                continue

            seen_hashes.add(r["hash"])
            enriched.append(r)

        # ✅ Adaptive re-query if too few items
        if len(enriched) < min_required:
            logging.info(f"[Collector] Evidence count low ({len(enriched)}). Broadening search...")
            extra_results = self.search_engine.search(user_query + " overview", limit=20)
            extra_results = self._filter_results_with_llm(user_query, extra_results, max_tokens=max_tokens)
            for r in extra_results:
                if r.get("snippet"):
                    r["compressed"] = r["snippet"][:800]
                    r["hash"] = file_hash(r["compressed"])
                    if r["hash"] not in seen_hashes:
                        enriched.append(r)
                        seen_hashes.add(r["hash"])

        # ✅ Researcher fallback if still too few
        if researcher and len(enriched) < min_required:
            logging.info(f"[Collector] Still low evidence ({len(enriched)}). Calling Researcher...")
            deep_ev = researcher.deep_search({"title": user_query}, user_query)
            for r in deep_ev:
                if r["hash"] not in seen_hashes:
                    enriched.append(r)
                    seen_hashes.add(r["hash"])

        # Local evidence ingestion
        if local_dir and os.path.isdir(local_dir):
            enriched.extend(self.ingest_local_files(local_dir))

        return enriched