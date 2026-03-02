import os
import json
from utils.helpers import safe_name, now_ts, slugify_query
from utils.token_counter import TokenCounter
from utils.persistence import save_evidence
from roles.planner import Planner
from roles.decomposer import Decomposer
from roles.collector import Collector
from roles.editor import Editor
from roles.auditor import Auditor
from roles.specialist import Specialist
from roles.supervisor import Supervisor
from roles.fulfillment import FulfillmentChecker
from roles.critical import CriticalThinker
from roles.integrator import Integrator
from roles.interpreter import Interpreter
from roles.finalizer import Finalizer
from roles.researcher import Researcher
from utils.llm_interface import LLMInterface
# from tqdm import tqdm
import logging
from colorama import Fore, Style, init
from utils.config import LLM_CFG
from utils.search_engine import SearxSearch
from utils.section_runner import run_sections
import glob
init(autoreset=True)

class Orchestrator:
    def __init__(self, language_hint="English", max_rounds=3, limit=20, local_evidence_dir=None, report_style="standard"):
        self.language_hint = language_hint
        self.max_rounds = max_rounds
        self.local_evidence_dir = local_evidence_dir
        self.report_style = report_style  # "standard" or "wiki"
        self.tokens = TokenCounter()
        self.llm = LLMInterface(self.tokens)
        self.limit = limit
        self.search_engine = SearxSearch(base_url="http://localhost:8888")
        self.project_id = f"{slugify_query(language_hint)}_{now_ts()}"
        self.collector = Collector(self.search_engine, self.project_id, self.limit, self.llm)
        self.planner = Planner(self.llm, self.tokens)
        self.decomposer = Decomposer(self.llm, self.tokens)
        self.editor = Editor(self.llm, self.tokens)
        self.auditor = Auditor(self.llm, self.tokens)
        self.specialist = Specialist(self.llm, self.tokens)
        self.supervisor = Supervisor(self.llm, self.tokens)
        self.fulfillment = FulfillmentChecker(self.llm, self.tokens)
        self.critical = CriticalThinker(self.llm, self.tokens)
        self.integrator = Integrator(self.llm, self.tokens)
        self.Interpreter = Interpreter(self.llm, self.tokens)
        self.Finalizer = Finalizer(self.llm, self.tokens)
        self.researcher = Researcher(self.search_engine, self.project_id, self.llm, self.limit)

    def run(self, user_query: str, max_tokens=None):
        self.max_tokens = max_tokens or LLM_CFG.max_tokens
        interpretation = self.Interpreter.interpret(user_query, max_tokens=self.max_tokens)
        logging.info(f"[Interpretation]:done")
        plan = self.planner.plan(interpretation, max_tokens=self.max_tokens)
        logging.info(f"[Planner]:done with {len(plan['sections'])} section")
        # sources = self.collector.collect(user_query, max_tokens=self.max_tokens)
        # logging.info(f"[Collector]:done")
        slug = slugify_query(user_query, max_words=5, max_len=50)
        project_id = f"{slug}_{now_ts()}"
        os.makedirs(project_id, exist_ok=True)
        os.makedirs(os.path.join(project_id, "evidence"), exist_ok=True)
        os.makedirs(os.path.join(project_id, "sections"), exist_ok=True)
        with open(os.path.join(project_id, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        iteration_history = []
        cumulative_sources = []
        prev_total = 0
        prev_round_outputs = {}  # store outputs per section
        fresh_sources = self.collector.collect(user_query, deep_visit=True, local_dir=self.local_evidence_dir)
        evidence_paths = save_evidence(project_id, fresh_sources)
        # Outer loop: rounds
        # for round_num in tqdm(range(1, self.max_rounds + 1), desc="Orchestration rounds", unit="round"):
        for round_num in range(1, self.max_rounds + 1):
            logging.info(f"=== Round {round_num} start ===")

            # Step 1: Collector (shallow evidence)
            fresh_sources = self.collector.collect(
                plan.get("query", ""),
                deep_visit=False,
                local_dir=self.local_evidence_dir
            )

            # Step 2: Section runner with Researcher fallback
            section_outputs = run_sections(
                plan.get("query", ""),
                plan["sections"],
                project_id,
                round_num,
                fresh_sources,
                prev_round_outputs,
                self.language_hint,
                self.max_tokens,
                self.fulfillment,
                self.critical,
                self.supervisor,
                self.editor,
                self.auditor,
                self.specialist,
                self.researcher,   # ✅ pass Researcher here
                min_required=10    # threshold for evidence count
            )

            # Update prev_round_outputs
            prev_round_outputs.update({o["section"]["id"]: o for o in section_outputs})

            # Scoring & iteration history
            avg_overall = sum(o["score"].get("overall", 0.0) for o in section_outputs) / max(1, len(section_outputs))
            iteration_history.append({
                "round": round_num,
                "avg_overall": avg_overall,
                "sections": section_outputs
            })

            with open(os.path.join(project_id, "iteration_history.json"), "w", encoding="utf-8") as f:
                json.dump(iteration_history, f, ensure_ascii=False, indent=2)

            if avg_overall >= 8.0:
                logging.info(f"[Round {round_num}] Quality threshold met, stopping early.")
                break
                
        # --- Final integration ---
        if iteration_history:
            # ✅ pick the round with the highest avg_overall
            best_round = max(iteration_history, key=lambda r: r["avg_overall"])
            logging.info(f"[orchestrator.run] max_rounds={self.max_rounds}, Using round {best_round['round']} with avg_overall={best_round['avg_overall']:.2f}")
            executive_summary = self.integrator.write_summary( best_round["sections"], self.language_hint, max_tokens=self.max_tokens )
            with open(os.path.join(project_id, "executive_summary.md"), "w", encoding="utf-8") as f:
                f.write(executive_summary)
            draft_final_report = self.integrator.integrate(
                best_round["sections"],
                executive_summary,
                self.language_hint,
                max_tokens=self.max_tokens,
                style=self.report_style  # pass style
            )
            with open(os.path.join(project_id, "draft_final_report.md"), "w", encoding="utf-8") as f:
                f.write(draft_final_report)

            final_report = self.Finalizer.polish_report( draft_final_report, language_hint=self.language_hint, max_tokens=self.max_tokens)
            report_path = os.path.abspath(os.path.join(project_id, "final_report.md"))
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(final_report)
            print("Final professional report saved at:", report_path)
        else:
            logging.warning("No iteration history; skipping final_report.md")
            # with open(os.path.join(project_id, "history.json"), "w", encoding="utf-8") as f:
                # json.dump(iteration_history, f, ensure_ascii=False, indent=2)
            # with open(os.path.join(project_id, "evidence_pool.json"), "w", encoding="utf-8") as f:
                # json.dump(cumulative_sources, f, ensure_ascii=False, indent=2)
            # with open(os.path.join(project_id, "manifest.json"), "w", encoding="utf-8") as f:
                # json.dump(manifest, f, ensure_ascii=False, indent=2)
            # print("Final professional report saved at:", report_path)
        # else:
            # logging.warning("No iteration history; skipping final_report.md and history.json")
            
        if iteration_history:
            final_avg = iteration_history[-1]["avg_overall"]
            if final_avg >= 8.0:
                banner_color = Fore.GREEN
                banner_text = "✅ SUCCESS: High-quality report generated"
            elif final_avg >= 5.0:
                banner_color = Fore.YELLOW
                banner_text = "⚠️ REVIEW: Report acceptable but improvements suggested"
            else:
                banner_color = Fore.RED
                banner_text = "❌ NEEDS IMPROVEMENT: Report quality below threshold"
            print(banner_color + "\n" + "="*60)
            print(banner_text.center(60))
            print("="*60 + Style.RESET_ALL)
            # --- Token Usage Summary Banner ---
            token_summary = { "total": self.tokens.total, "by_role": self.tokens.all_usage() }
            print(Fore.CYAN + "\n" + "="*60)
            print("📊 TOKEN USAGE SUMMARY".center(60))
            print("="*60 + Style.RESET_ALL)
            print(f"Total tokens used: {token_summary['total']}")
            print("Per-role breakdown:")
            for role, usage in token_summary["by_role"].items():
                print(f"{role:<12} prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} total={usage['total_tokens']}")
        else:
            print(Fore.RED + "\n" + "="*60)
            print("❌ NO REPORT GENERATED".center(60))
            print("="*60 + Style.RESET_ALL)
        return {
            "project_id": project_id,
            "final_report_path": os.path.join(project_id, "final_report.md"),
            "iteration_history": iteration_history,
            "token_summary": {"total": self.tokens.total, "by_role": self.tokens.role_usage}
        }

    def resume(self, project_dir: str, max_tokens=None):
        """
        Resume an interrupted orchestration run.
        - Load plan.json from project_dir
        - Load evidence JSON files
        - Load iteration history if available
        - Continue remaining rounds until max_rounds or quality threshold
        """

        # Load iteration history
        history_path = os.path.join(project_dir, "iteration_history.json")
        iteration_history = []
        last_round = 0
        if os.path.isfile(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                iteration_history = json.load(f)
            if iteration_history:
                last_round = iteration_history[-1]["round"]
            logging.info("[Resume] Loaded iteration history with %d rounds", len(iteration_history))
        else:
            logging.warning("[Resume] No iteration_history.json found, starting fresh")

        self.max_tokens = max_tokens or LLM_CFG.max_tokens

        # Load plan
        plan_path = os.path.join(project_dir, "plan.json")
        if not os.path.isfile(plan_path):
            raise RuntimeError(f"plan.json not found in {project_dir}")
        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)

        # Load evidence pool
        evidence_dir = os.path.join(project_dir, "evidence")
        evidence_files = glob.glob(os.path.join(evidence_dir, "*.json"))
        cumulative_sources = []
        for ef in evidence_files:
            try:
                with open(ef, "r", encoding="utf-8") as f:
                    cumulative_sources.append(json.load(f))
            except Exception as e:
                logging.warning("Failed to load evidence %s: %s", ef, e)

        # Load previous drafts into prev_round_outputs
        sections_dir = os.path.join(project_dir, "sections")
        prev_round_outputs = {}
        if os.path.isdir(sections_dir):
            for sec_id in os.listdir(sections_dir):
                sec_path = os.path.join(sections_dir, sec_id)
                if os.path.isdir(sec_path):
                    md_files = glob.glob(os.path.join(sec_path, "*.md"))
                    if md_files:
                        latest_md = max(md_files, key=os.path.getmtime)
                        try:
                            with open(latest_md, "r", encoding="utf-8") as f:
                                content = f.read()
                            prev_round_outputs[sec_id] = {
                                "section": {"id": sec_id, "title": sec_id},
                                "draft": content,
                                "audit": "",
                                "critical": "",
                                "score": {"overall": 6.0, "improvements": ["resume refinement"]}
                            }
                        except Exception as e:
                            logging.warning("Failed to load completed section %s: %s", sec_id, e)

        logging.info("[Resume] Loaded plan with %d sections", len(plan.get("sections", [])))
        logging.info("[Resume] Loaded %d evidence files", len(cumulative_sources))
        logging.info("[Resume] Detected %d sections with previous drafts", len(prev_round_outputs))

        prev_total = self.tokens.total

        # Outer loop: continue from last_round + 1
        for round_num in range(last_round + 1, self.max_rounds + 1):
            logging.info(f"=== Resume Round {round_num} start ===")

            # Collect fresh evidence
            fresh_sources = self.collector.collect(
                plan.get("query", ""),
                deep_visit=True,
                local_dir=self.local_evidence_dir
            )
            evidence_paths = save_evidence(project_dir, fresh_sources)

            # Run all sections, using prev_round_outputs for refinement
            section_outputs = run_sections(
                plan.get("query", ""),
                plan["sections"],
                project_dir,
                round_num,
                fresh_sources,
                prev_round_outputs,
                self.language_hint,
                self.max_tokens,
                self.fulfillment,
                self.critical,
                self.supervisor,
                self.editor,
                self.auditor,
                self.specialist,
                self.researcher
            )

            prev_round_outputs.update({o["section"]["id"]: o for o in section_outputs})

            round_tokens = self.tokens.total - prev_total
            avg_overall = sum(o["score"].get("overall", 0.0) for o in section_outputs) / max(1, len(section_outputs))
            total_improvements = sum(len(o["score"].get("improvements", [])) for o in section_outputs)
            logging.info(f"[Resume Round {round_num}] avg_overall={avg_overall:.2f}, improvements={total_improvements}, tokens_used={round_tokens}")
            prev_total = self.tokens.total

            iteration_history.append({
                "round": round_num,
                "avg_overall": avg_overall,
                "tokens_used": round_tokens,
                "tokens_total": self.tokens.total,
                "sections": section_outputs
            })

            # Stop if threshold met
            if avg_overall >= 8.0:
                break

        # Final integration
        if iteration_history:
            executive_summary = self.integrator.write_summary(
                iteration_history[-1]["sections"], self.language_hint, max_tokens=self.max_tokens
            )
            draft_final_report = self.integrator.integrate(
                iteration_history[-1]["sections"], executive_summary, self.language_hint, max_tokens=self.max_tokens
            )
            final_report = self.Finalizer.polish_report(
                draft_final_report, self.language_hint, max_tokens=self.max_tokens
            )
            report_path = os.path.abspath(os.path.join(project_dir, "final_report.md"))
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(final_report)
            with open(os.path.join(project_dir, "executive_summary.md"), "w", encoding="utf-8") as f:
                f.write(executive_summary)
            print("Final professional report saved at:", report_path)
        else:
            logging.warning("[Resume] No iteration history; skipping final_report.md")

        return {
            "project_id": os.path.basename(project_dir),
            "final_report_path": os.path.join(project_dir, "final_report.md"),
            "iteration_history": iteration_history,
            "token_summary": {"total": self.tokens.total, "by_role": self.tokens.role_usage}
        }
