"""
agents/planner.py  
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from schemas.planner import (QueryIntent, ToolName, StepStatus, PlanStep, ExecutionPlan)
from schemas.intent import IntentOutput
logger = logging.getLogger(__name__)


class PlannerAgent:
    """
    Converts a raw intent dict (from HuggingFace) into an ExecutionPlan.

    Design decisions
    ----------------
    * Intent is always a plain dict — no mixed dict/attr access.
    * Step IDs are assigned after conditional filtering so depends_on
      references remain consistent.
    * Plans are immutable snapshots; 
    * Low-confidence intents short-circuit to a cheaper plan variant.
    """

    # Time estimates per tool (seconds) — used for scheduling 
    _TOOL_TIME: Dict[ToolName, float] = {
        ToolName.KEYWORD_SCRAPER:        10.0,
        ToolName.PRODUCT_DETAIL_SCRAPER: 10.0,
        ToolName.PRICE_FILTER:            1.5,
        ToolName.DIETARY_FILTER:          1.5,
        ToolName.FLAVOUR_FILTER:          1.3,
        ToolName.BRAND_FILTER:            1.3,
        ToolName.NUTRITION_RANKER:        1.0,
        ToolName.COMPOSITE_RANKER:        1.0,
        ToolName.COMPARISON_ENGINE:       2.0,
        ToolName.RESPONSE_GENERATOR:      2.0,
    }

    # Plan templates  (logical step definitions, IDs assigned at build time)
    # Each entry:
    #   tool            — ToolName
    #   description     — human-readable
    #   save_as         — variable name for executor context
    #   param_paths     — dict of param_key → dotted path into intent
    #                     (use None value for literal values)
    #   literal_params  — dict of param_key → literal value
    #   depends_on_refs — list of save_as strings this step depends on
    #   condition_path  — dotted intent path; step skipped if value is None
    #   retry_on_failure
    #   fallback_ref    — save_as of step to activate on failure (optional)
    #   reasoning       — override auto-generated reasoning


    _TEMPLATES: Dict[str, List[Dict[str, Any]]] = {

        QueryIntent.RECOMMENDATION: [
            {
                "tool":            ToolName.KEYWORD_SCRAPER,
                "description":     "Scrape products using suggested keywords",
                "save_as":         "scraped_products",
                "param_paths":     {"keywords": "suggested_keywords"},
                "literal_params":  {"fetch_details": True},
                "depends_on_refs": [],
            },
            {
                "tool":            ToolName.NUTRITION_RANKER,
                "description":     "Rank by nutritional value",
                "save_as":         "ranked_products",
                "param_paths":     {},
                "literal_params":  {"criteria": "balanced", "products": "scraped_products"},
                "depends_on_refs": ["scraped_products"],
            },
            {
                "tool":            ToolName.RESPONSE_GENERATOR,
                "description":     "Format results for the user",
                "save_as":         "final_response",
                "param_paths":     {},
                "literal_params":  {},
                "depends_on_refs": ["ranked_products"],
            },
        ],

        QueryIntent.BUDGET: [
            {
                "tool":            ToolName.KEYWORD_SCRAPER,
                "description":     "Scrape products with price-aware keywords",
                "save_as":         "scraped_products",
                "param_paths":     {"keywords": "suggested_keywords"},
                "literal_params":  {"fetch_details": True},
                "depends_on_refs": [],
            },
            {
                "tool":             ToolName.PRICE_FILTER,
                "description":      "Keep products within budget",
                "save_as":          "budget_products",
                "param_paths":      {"max_price": "entities.max_price", "products": "scraped_products"},
                "literal_params":   {},
                "depends_on_refs":  ["scraped_products"],
                "retry_on_failure": True,
                "fallback_ref":     "ranked_products",   # skip filter if it yields zero
            },
            {
                "tool":            ToolName.COMPOSITE_RANKER,
                "description":     "Rank by value-for-money ratio",
                "save_as":         "ranked_products",
                "param_paths":     {"max_price": "entities.max_price", "products": "scraped_products"},
                "literal_params":  {"criteria": "value_for_money"},
                "depends_on_refs": ["budget_products"],
            },
            {
                "tool":            ToolName.RESPONSE_GENERATOR,
                "description":     "Format budget-aware results",
                "save_as":         "final_response",
                "param_paths":     {},
                "literal_params":  {"include_budget_alternatives": True},
                "depends_on_refs": ["ranked_products"],
            },
        ],

        QueryIntent.GOAL_BASED: [
            {
                "tool":            ToolName.KEYWORD_SCRAPER,
                "description":     "Scrape products matching health goal",
                "save_as":         "scraped_products",
                "param_paths":     {"keywords": "suggested_keywords"},
                "literal_params":  {"fetch_details": True},
                "depends_on_refs": [],
            },
            {
                "tool":             ToolName.DIETARY_FILTER,
                "description":      "Filter by dietary constraints",
                "save_as":          "dietary_products",
                "param_paths":      {"constraints": "entities.dietary_constraints", "products": "scraped_products"},
                "literal_params":   {},
                "depends_on_refs":  ["scraped_products"],
                "retry_on_failure": True,
                "reasoning":        "Must match dietary requirements strictly",
            },
            {
                "tool":            ToolName.FLAVOUR_FILTER,
                "description":     "Apply flavour preference if specified",
                "save_as":         "flavour_products",
                "param_paths":     {"flavour": "entities.flavour", "products": "scraped_products"},
                "literal_params":  {},
                "depends_on_refs": ["dietary_products"],
                "condition_path":  "entities.flavour",   # skip if None
            },
            {
                "tool":            ToolName.NUTRITION_RANKER,
                "description":     "Rank by health metrics",
                "save_as":         "ranked_products",
                "param_paths":     {
                                      "criteria":             "primary_intent",
                                      "dietary_constraints":  "entities.dietary_constraints",
                                   },
                "literal_params":  {},
                # depends on flavour_products if that step ran, else dietary_products
                "depends_on_refs": ["flavour_products", "dietary_products"],
                "depends_on_any":  True,   # first available wins
            },
            {
                "tool":            ToolName.RESPONSE_GENERATOR,
                "description":     "Format health-focused results",
                "save_as":         "final_response",
                "param_paths":     {},
                "literal_params":  {"include_health_analysis": True},
                "depends_on_refs": ["ranked_products"],
            },
        ],
    }

    def create_plan(
        self,
        query:           str,
        intent:          IntentOutput,
        available_tools: Optional[List[ToolName]] = None,
    ) -> ExecutionPlan:
        """
        Build an ExecutionPlan from a raw intent dict.

        Raises
        ------
        ValueError
            If any required intent field is missing and the caller should
            send a clarification back to the user.
        """
        primary_intent = intent.get("primary_intent", QueryIntent.RECOMMENDATION)
        confidence     = intent.get("confidence", 1.0)

        template_steps = self._TEMPLATES.get(
            primary_intent,
            self._TEMPLATES[QueryIntent.RECOMMENDATION],   # safe fallback
        )

        logger.info(
            "Building plan",
            extra={
                "query":          query,
                "primary_intent": primary_intent,
                "confidence":     confidence,
            },
        )

        # 1. Filter conditional steps
        active_templates = self._apply_conditions(template_steps, intent)

        # 2. Assign sequential IDs and build save_as → id map
        save_as_to_id: Dict[str, int] = {}
        raw_steps: List[Dict[str, Any]] = []

        for idx, tmpl in enumerate(active_templates, start=1):
            save_as_to_id[tmpl["save_as"]] = idx
            raw_steps.append({**tmpl, "_assigned_id": idx})

        # 3. Resolve depends_on references → actual IDs
        steps: List[PlanStep] = []
        for tmpl in raw_steps:
            step_id  = tmpl["_assigned_id"]
            dep_ids  = self._resolve_dependencies(tmpl, save_as_to_id)
            params   = self._resolve_params(tmpl, intent)
            fallback_id = (
                save_as_to_id.get(tmpl.get("fallback_ref"))
                if tmpl.get("fallback_ref")
                else None
            )
            reasoning = tmpl.get(
                "reasoning",
                self._auto_reasoning(tmpl["tool"], intent, step_id),
            )

            step = PlanStep(
                step_id          = step_id,
                tool             = tmpl["tool"],
                description      = tmpl["description"],
                params           = params,
                depends_on       = dep_ids,
                save_output_as   = tmpl["save_as"],
                retry_on_failure = tmpl.get("retry_on_failure", False),
                max_retries      = tmpl.get("max_retries", 1),
                fallback_step    = fallback_id,
                reasoning        = reasoning,
            )

            if available_tools and step.tool not in available_tools:
                step.status    = StepStatus.SKIPPED
                step.reasoning += " [tool unavailable]"
                logger.warning("Tool unavailable, step skipped", extra={"tool": step.tool})

            steps.append(step)

        # 4. Validate required params are not None
        self._validate_params(steps, intent)

        # 5. Confidence-based short circuit
        if confidence < 0.5:
            steps = self._apply_low_confidence_fallback(steps, intent)
            logger.warning("Low confidence — applying cheap plan", extra={"confidence": confidence})

        plan = ExecutionPlan(
            plan_id           = f"plan_{primary_intent}_{uuid.uuid4().hex[:8]}",
            query             = query,
            intent            = intent,
            steps             = steps,
            estimated_time_s  = self._estimate_time(steps),
            total_steps       = len(steps),
            requires_scraping = any(s.tool == ToolName.KEYWORD_SCRAPER for s in steps),
            requires_ranking  = any(
                s.tool in (ToolName.NUTRITION_RANKER, ToolName.COMPOSITE_RANKER)
                for s in steps
            ),
        )

        logger.info(
            "Plan created",
            extra={
                "plan_id":           plan.plan_id,
                "steps":             plan.total_steps,
                "estimated_time_s":  plan.estimated_time_s,
            },
        )
        return plan

    def _apply_conditions(
        self,
        templates: List[Dict[str, Any]],
        intent:    IntentOutput,
    ) -> List[Dict[str, Any]]:
        """Remove steps whose condition_path resolves to None in intent."""
        active = []
        for tmpl in templates:
            cond_path = tmpl.get("condition_path")
            if cond_path is not None:
                value = self._nested_get(intent, cond_path)
                if value is None:
                    logger.debug(
                        "Skipping step (condition not met)",
                        extra={"save_as": tmpl["save_as"], "condition_path": cond_path},
                    )
                    continue
            active.append(tmpl)
        return active

    def _resolve_dependencies(
        self,
        tmpl:          Dict[str, Any],
        save_as_to_id: Dict[str, int],
    ) -> List[int]:
        """
        Resolve depends_on_refs → step IDs.
        When depends_on_any=True only the first ref that has an ID is used
        (covers the case where a conditional step may or may not be present).
        """
        refs      = tmpl.get("depends_on_refs", [])
        any_mode  = tmpl.get("depends_on_any", False)

        if any_mode:
            for ref in refs:
                if ref in save_as_to_id:
                    return [save_as_to_id[ref]]
            return []

        return [save_as_to_id[r] for r in refs if r in save_as_to_id]

    def _resolve_params(
        self,
        tmpl:   Dict[str, Any],
        intent: IntentOutput,
    ) -> Dict[str, Any]:
        """
        Merge param_paths (resolved from intent) with literal_params.
        param_paths values that resolve to None are included — callers
        must handle optional params.
        """
        resolved: Dict[str, Any] = {}

        for key, path in tmpl.get("param_paths", {}).items():
            resolved[key] = self._nested_get(intent, path)

        resolved.update(tmpl.get("literal_params", {}))
        return resolved

    @staticmethod
    def _nested_get(obj: Any, path: str) -> Any:
        """Dot-notation accessor for nested dicts."""
        current = obj
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
            if current is None:
                return None
        return current

    def _validate_params(self, steps: List[PlanStep], intent: IntentOutput) -> None:
        """
        Warn when a step receives None for a param that is likely required.
        Extend this dict to make validation strict (raise ValueError) for prod.
        """
        required_by_tool: Dict[ToolName, List[str]] = {
            ToolName.PRICE_FILTER:    ["max_price"],
            ToolName.DIETARY_FILTER:  ["constraints"],
            ToolName.KEYWORD_SCRAPER: ["keywords"],
        }
        for step in steps:
            if step.status == StepStatus.SKIPPED:
                continue
            for required_param in required_by_tool.get(step.tool, []):
                if step.params.get(required_param) is None:
                    logger.warning(
                        "Required param is None — step may fail",
                        extra={
                            "step_id": step.step_id,
                            "tool":    step.tool,
                            "param":   required_param,
                        },
                    )

    def _apply_low_confidence_fallback(
        self,
        steps:  List[PlanStep],
        intent: IntentOutput,
    ) -> List[PlanStep]:
        """
        On low confidence: skip scraping and go straight to response,
        asking the user for clarification. Extend this for a cached-result path.
        """
        clarification_q = intent.get("clarification_question")
        for step in steps:
            if step.tool not in (ToolName.RESPONSE_GENERATOR,):
                step.status    = StepStatus.SKIPPED
                step.reasoning += " [skipped: low confidence]"

        # Inject clarification param into response generator
        for step in steps:
            if step.tool == ToolName.RESPONSE_GENERATOR:
                step.depends_on              = []
                step.params["clarification"] = clarification_q or (
                    "Could you clarify what you're looking for?"
                )
        return steps

    def _estimate_time(self, steps: List[PlanStep]) -> float:
        """
        Estimate wall-clock time accounting for parallel execution.
        Builds a simple DAG cost model: each "wave" of dependency-free steps
        runs in parallel; cost = max(tool_times) per wave.
        """
        remaining     = [s for s in steps if s.status != StepStatus.SKIPPED]
        completed_ids: set = set()
        total_time    = 0.0

        while remaining:
            # Steps whose deps are all satisfied
            wave = [
                s for s in remaining
                if all(dep in completed_ids for dep in s.depends_on)
            ]
            if not wave:
                break  

            wave_time  = max(self._TOOL_TIME.get(s.tool, 1.0) for s in wave)
            total_time += wave_time
            for s in wave:
                completed_ids.add(s.step_id)
            remaining = [s for s in remaining if s not in wave]

        return total_time

    def _auto_reasoning(self, tool: ToolName, intent: IntentOutput, step_id: int) -> str:
        entities = intent.get("entities", {})
        msgs: Dict[ToolName, str] = {
            ToolName.KEYWORD_SCRAPER:    f"Find products for '{intent.get('primary_intent')}' "
                                         f"using: {intent.get('suggested_keywords', [])}",
            ToolName.PRICE_FILTER:       f"Budget constraint ₹{entities.get('max_price')} — must filter",
            ToolName.DIETARY_FILTER:     f"Dietary requirements: {entities.get('dietary_constraints')}",
            ToolName.FLAVOUR_FILTER:     f"Flavour preference: {entities.get('flavour')}",
            ToolName.NUTRITION_RANKER:   "Rank by nutritional value — aligns with health query",
            ToolName.COMPOSITE_RANKER:   "Multi-factor ranking for value recommendation",
            ToolName.COMPARISON_ENGINE:  "Head-to-head comparison for 'compare' intent",
            ToolName.RESPONSE_GENERATOR: "Final step — format results for user",
        }
        return msgs.get(tool, f"Step {step_id}: {tool.value}")