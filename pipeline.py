# pipeline.py

import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.intent_router import IntentRouter
from agents.planner import PlannerAgent, ToolName
from agents.executor import ExecutorAgent
from schemas.response import PipelineResult


class RecommendationPipeline:
    """
    Main orchestrator — Planner produces the DAG, Pipeline executes it.

    Data flow
    ---------
    Each tool executor returns a value which is stored in self.context
    under the step's save_output_as key.  Before a step runs, _hydrate_params
    replaces any param whose value is a context key string with the actual
    stored object, so tools always receive real data, never key names.
    """

    def __init__(self, spider_instance, logger):
        self.logger = logger
        self.intent_router    = IntentRouter(logger)
        self.planner          = PlannerAgent()
        self.executor         = ExecutorAgent(spider_instance, logger)
        self.context: Dict[str, Any] = {}

    def launch_job(
        self,
        query:     str,
        pincode:   str = "302006",
        latitude:  str = "26.9059311",
        longitude: str = "75.78443829999999",
    ) -> PipelineResult:

        query_id   = str(uuid.uuid4().hex)[:16]
        start_time = time.time()
        errors: List[str] = []

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Pipeline Started | Query ID: {query_id}\n")
        self.logger.info(f"Query: '{query}'")
        self.logger.info(f"{'='*60}")

        # seed context with request-level values every tool can read
        self.context = {
            "query":     query,
            "pincode":   pincode,
            "latitude":  latitude,
            "longitude": longitude,
        }

        # ── STEP 1: Intent classification
        self.logger.info("STEP 1: Intent Classification...")
        intent = self.intent_router.classify_intent(query)
        
        self.context["intent"] = intent

        # ── STEP 2: Building execution plan 
        self.logger.info("STEP 2: Creating Execution Plan...")
        plan = self.planner.create_plan(query, intent)

        primary_intent = intent.get("primary_intent", "recommendation")
        self.logger.info(f"Plan ID  : {plan.plan_id}")
        self.logger.info(f"Intent   : {primary_intent}")
        self.logger.info(f"Est. time: {plan.estimated_time_s:.1f}s")
        self.logger.info(f"Steps ({plan.total_steps}):")
        for step in plan.steps:
            self.logger.info(f"      {step.step_id}. [{step.tool.value}] {step.description}")
            self.logger.info(f"         Reason : {step.reasoning}")
            if step.depends_on:
                self.logger.info(f"         Depends: {step.depends_on}")

        # ── STEP 3: Executing the plan ────────────────────────────────────────
        self.logger.info(f"\n  STEP 3: Executing Plan...\n {plan}")
        self.executor._execute_plan(plan, errors, self.context)

        execution_time = time.time() - start_time

        ranked_products = self.context.get("ranked_products", [])
        response_text   = self.context.get("final_response", "No response generated")

        result = PipelineResult(
            query_id               = query_id,
            original_query         = query,
            pincode                = pincode,
            intent                 = intent,
            products_scraped       = self.context.get("products_scraped", 0),
            products_filtered      = self.context.get("products_filtered", 0),
            ranked_products        = ranked_products,
            response_text          = response_text,
            execution_time_seconds = round(execution_time, 2),
            errors                 = errors,
            completed_at           = datetime.now(),
        )

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Pipeline Complete | Time: {execution_time:.2f}s | Errors: {len(errors)}")
        self.logger.info(f"{'='*60}")

        return result
