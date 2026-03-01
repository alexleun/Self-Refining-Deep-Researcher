import os
import logging
import json
from tqdm import tqdm
from utils.helpers import safe_name

#--------------
# def run_sections(user_query, sections, project_id,round_num, fresh_sources, prev_round_outputs, language_hint, max_tokens,
# fulfillment, criticalThinker, supervisor, editor, auditor, Specialist):
    # """
    # Externalized inner loop for orchestrator.
    # Handles section drafting, auditing, and artifact saving.
    # """
    # section_outputs = []

    # # Inner loop: sections with progress bar
    # # for sec in tqdm(sections, desc=f"Round {round_num} sections", unit="section", leave=False):
    # for sec in sections:
        # logging.info(f"[section_runner] Process Section:{sec[1]} {sec[3]}")
        # sec_dir = os.path.join(project_id, "sections", safe_name(sec.get("id", sec.get("title", "sec"))))
        # os.makedirs(sec_dir, exist_ok=True)
        # ev = fresh_sources
        
        # # 🔑 Pull previous round artifacts if available
        # prev = prev_round_outputs.get(sec["id"], {})
        # prev_draft = prev.get("draft", "")
        # prev_audit = prev.get("audit", "")
        # prev_critical = prev.get("critical", "")
        # # Editor now refines based on previous draft + audit + critical
        
        # draft = editor.draft_section(sec, ev, language_hint , prev_draft=prev_draft, prev_audit=prev_audit, max_tokens=max_tokens)
        # with open(os.path.join(sec_dir, f"original_draft_round{round_num}.md"), "w", encoding="utf-8") as f:
            # f.write(draft)
        # audit = auditor.audit_section(draft, ev, max_tokens=max_tokens)
        # with open(os.path.join(sec_dir, f"audit_round{round_num}.md"), "w", encoding="utf-8") as f:
            # f.write(audit)
        # enriched = Specialist.enrich(draft, audit,  max_tokens=max_tokens)
        # with open(os.path.join(sec_dir, f"draft_round{round_num}.md"), "w", encoding="utf-8") as f:
            # f.write(enriched)
        # score = supervisor.score(enriched,  max_tokens=max_tokens)
        # with open(os.path.join(sec_dir, f"score_round{round_num}.json"), "w", encoding="utf-8") as f:
            # json.dump(score, f, ensure_ascii=False, indent=2)
        # fulfill = fulfillment.check(user_query, enriched,  max_tokens=max_tokens)
        # with open(os.path.join(sec_dir, f"fulfillment_round{round_num}.md"), "w", encoding="utf-8") as f:
            # f.write(fulfill)
        # critical = criticalThinker.questions(enriched, max_tokens=max_tokens)
        # # Save artifacts
        # with open(os.path.join(sec_dir, f"critical_round{round_num}.md"), "w", encoding="utf-8") as f:
            # f.write(critical)
        # section_outputs.append({"section": sec, "draft": enriched, "audit": audit, "score": score, "fulfillment": fulfill, "critical": critical })
    # return section_outputs
# ---------------

def run_sections(user_query, sections, project_id, round_num, fresh_sources, prev_round_outputs,
                 language_hint, max_tokens,
                 fulfillment, criticalThinker, supervisor, editor, auditor, Specialist, researcher,
                 min_required=10):
    """
    Extended inner loop with Researcher fallback.
    """
    section_outputs = []

    for sec in sections:
        logging.info(f"[section_runner] Process Section:{sec['id']} {sec['title']}")
        sec_dir = os.path.join(project_id, "sections", safe_name(sec.get("id", sec.get("title", "sec"))))
        os.makedirs(sec_dir, exist_ok=True)

        # Base evidence
        ev = fresh_sources

        # 🔑 Pull previous round artifacts if available
        prev = prev_round_outputs.get(sec["id"], {})
        prev_draft = prev.get("draft", "")
        prev_audit = prev.get("audit", "")
        prev_critical = prev.get("critical", "")

        # ✅ Evidence check
        if len(ev) < min_required and researcher:
            logging.info(f"[section_runner] Evidence low ({len(ev)}). Calling Researcher for section {sec['id']}")
            deep_ev = researcher.deep_search(sec, user_query, prev_audit, prev_critical)
            if deep_ev:
                ev = ev + deep_ev

        # Editor draft
        draft = editor.draft_section(sec, ev, language_hint,
                                     prev_draft=prev_draft, prev_audit=prev_audit, max_tokens=max_tokens)
        with open(os.path.join(sec_dir, f"original_draft_round{round_num}.md"), "w", encoding="utf-8") as f:
            f.write(draft)

        # Auditor
        audit = auditor.audit_section(draft, ev, max_tokens=max_tokens)
        with open(os.path.join(sec_dir, f"audit_round{round_num}.md"), "w", encoding="utf-8") as f:
            f.write(audit)

        # Specialist enrichment
        enriched = Specialist.enrich(draft, audit, max_tokens=max_tokens)
        with open(os.path.join(sec_dir, f"draft_round{round_num}.md"), "w", encoding="utf-8") as f:
            f.write(enriched)

        # Supervisor scoring
        score = supervisor.score(enriched, max_tokens=max_tokens)
        with open(os.path.join(sec_dir, f"score_round{round_num}.json"), "w", encoding="utf-8") as f:
            json.dump(score, f, ensure_ascii=False, indent=2)

        # Fulfillment check
        fulfill = fulfillment.check(user_query, enriched, max_tokens=max_tokens)
        with open(os.path.join(sec_dir, f"fulfillment_round{round_num}.md"), "w", encoding="utf-8") as f:
            f.write(fulfill)

        # Critical questions
        critical = criticalThinker.questions(enriched, max_tokens=max_tokens)
        with open(os.path.join(sec_dir, f"critical_round{round_num}.md"), "w", encoding="utf-8") as f:
            f.write(critical)

        section_outputs.append({
            "section": sec,
            "draft": enriched,
            "audit": audit,
            "score": score,
            "fulfillment": fulfill,
            "critical": critical,
            "evidence_used": ev
        })

    return section_outputs