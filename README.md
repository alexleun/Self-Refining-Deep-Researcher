# Self‑Refining Deep Researcher

A modular, multi‑agent framework for **iterative research and report generation**.  
This project orchestrates specialized roles (Planner, Collector, Researcher, Editor, Auditor, Integrator, Finalizer) to transform a user query into a structured, evidence‑backed, polished report.

---

## ✨ Features
- **Intent Analysis**: interpret user query into goals, scope, and constraints.
- **Planner**: generate section/topic plan with search queries and acceptance criteria.
- **Collector**: perform quick evidence retrieval from the web.
- **Researcher (NEW)**: conduct deep, targeted searches for richer evidence and provenance.
- **Editor**: draft section content using collected evidence.
- **Auditor**: score drafts for factuality, clarity, and citation coverage.
- **Integrator**: merge drafts into an executive summary and full report.
- **Finalizer**: polish the report into professional or wiki style.
- **Iteration History**: track rounds, scores, and improvements in `iteration_history.json`.
- **Resume Support**: continue unfinished projects from saved state.

---

## 📂 Project Structure
```
main.py              # CLI entrypoint for fresh runs
resume.py            # CLI entrypoint for resuming projects
orchestrator.py      # Lifecycle controller
roles/
  ├─ auditor.py
  ├─ collector.py
  ├─ critical.py
  ├─ decomposer.py
  ├─ editor.py
  ├─ finalizer.py
  ├─ fulfillment.py
  ├─ integrator.py
  ├─ interpreter.py
  ├─ llm_interface.py
  ├─ planner.py
  ├─ specialist.py
  └─ researcher.py   # NEW deep research roles
data/
  ├─ evidence/       # JSON evidence files
  ├─ sections/       # Drafts per section per round
  ├─ iteration_history.json
  └─ project_manifest.json
utils/
  ├─ config.py
  ├─ helpers.py
  ├─ llm_interface.py
  ├─ logging_utils.py
  ├─ normalizer.py
  ├─ pdf_hander.py
  ├─ persistence.py
  ├─ logging_utils.py
  ├─ normalizer.py
  ├─ persistence.py
  ├─ prompt_compressor.py
  ├─ search_engine.py
  ├─ section_runner.py
  ├─ test_langchain_pipline.py
  └─ token_counter.py
```

---

## 🚀 Workflow
1. **Analyze Query** → extract intent, scope, language, style.
2. **Plan Sections** → generate `plan.json` with topics and queries.
3. **Collect Evidence** → quick retrieval of shallow sources.
4. **Deep Research** → researcher adds targeted, high‑quality evidence.
5. **Draft Sections** → editor writes drafts with citations.
6. **Audit Drafts** → auditor scores and suggests improvements.
7. **Iterate Rounds** → orchestrator loops until quality threshold or max rounds.
8. **Integrate & Finalize** → best round selected, executive summary + final report produced.

---

## ⚙️ Usage
Run a new project:
```bash
python main.py --query "Impacts of negative Arctic oscillation" --style standard --lang "English" --max-rounds 5 --max-tokens 20000
```

Resume an existing project:
```bash
python resume.py --project negative_arctic_oscillation_20260124_183224 --lang "Traditional Chinese" --max-rounds 5 --max-tokens 12791
```

---

## 📑 Output Artifacts
- `executive_summary.md` — concise overview.
- `draft_final_report.md` — integrated draft.
- `final_report.md` — polished professional or wiki‑style report.
- `iteration_history.json` — record of rounds, scores, and improvements.
- `evidence/*.json` — raw evidence with provenance metadata.

---

## 🛠️ Roadmap
- [ ] Add Researcher role for deep evidence.
- [x] Support wiki‑style report formatting.
- [ ] Enhance resume to continue missing rounds seamlessly.
- [ ] Add provenance mapping (claims → sources).
- [x] Expand auditor scoring schema.

---


Would you like me to also draft that **ARCHITECTURE.md** file, summarizing the internal design (roles, orchestrator, resume logic) so contributors have a deeper technical reference separate from the README?
