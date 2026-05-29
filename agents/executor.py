import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.planner import ExecutionPlan, StepStatus, ToolName
from agents.response_generator import ResponseGenerator
from tools.scraper_tool import ScraperTool
from tools.filter_tool import FilterTool
from tools.ranker_tool import RankerTool

class ExecutorAgent:
    def __init__(self, spider_instance, logger):
        self.tool_registry = {
            ToolName.KEYWORD_SCRAPER:    self._execute_scraper,
            ToolName.PRICE_FILTER:       self._execute_price_filter,
            ToolName.DIETARY_FILTER:     self._execute_dietary_filter,
            ToolName.FLAVOUR_FILTER:     self._execute_flavour_filter,
            ToolName.BRAND_FILTER:       self._execute_brand_filter,
            ToolName.NUTRITION_RANKER:   self._execute_nutrition_ranker,
            ToolName.COMPOSITE_RANKER:   self._execute_composite_ranker,
            ToolName.RESPONSE_GENERATOR: self._execute_response_generator,
        }
        self.scraper_tool = ScraperTool(spider_instance, logger)
        self.response_generator = ResponseGenerator(logger=logger)
        self.filter_tool  = FilterTool()
        self.ranker_tool  = RankerTool()
        self.logger = logger
        self.context = {}

    def _execute_plan(self, plan: ExecutionPlan, errors: list, context_list):
        """
        executing the flow based on DAG flow provided  
        """
        self.context = context_list
        completed_steps: set = set()
        failed_steps:    set = set()

        while True:
            ready_steps = [
                step for step in plan.steps
                if step.status == StepStatus.PENDING
                and all(dep in completed_steps for dep in step.depends_on)
            ]

            if not ready_steps:
                pending = [s for s in plan.steps if s.status == StepStatus.PENDING]
                if not pending:
                    break   # all done

                # mark steps whose dependency failed as skipped
                for step in pending:
                    if any(dep in failed_steps for dep in step.depends_on):
                        self.logger.warning(
                            f"Step {step.step_id} ({step.tool.value}) skipped "
                            f"— dependency failed"
                        )
                        step.status = StepStatus.SKIPPED
                break

            for step in ready_steps:
                if step.status == StepStatus.SKIPPED:
                    completed_steps.add(step.step_id)
                    continue

                self.logger.info(f"\n Step {step.step_id}: {step.description}")
                self.logger.info(f"Tool: {step.tool.value}")

                step.status = StepStatus.IN_PROGRESS

                executor = self.tool_registry.get(step.tool)
                if not executor:
                    msg = f"No executor registered for tool: {step.tool}"
                    self.logger.error(msg)
                    step.status = StepStatus.FAILED
                    failed_steps.add(step.step_id)
                    errors.append(f"Step {step.step_id}: {msg}")
                    continue

                try:
                    # resolve context references in params before calling tool
                    hydrated_params = self.update_params_structure(step.params)

                    result = executor(hydrated_params)

                    self.context[step.save_output_as] = result
                    step.status = StepStatus.COMPLETED
                    completed_steps.add(step.step_id)

                    self.logger.info(f"Saved '{step.save_output_as}'")

                except Exception as e:
                    self.logger.error(f"Step {step.step_id} failed: {e}", exc_info=True)
                    step.status = StepStatus.FAILED
                    failed_steps.add(step.step_id)
                    errors.append(f"Step {step.step_id} ({step.tool.value}): {str(e)}")

    def update_params_structure(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace context-key references with real values.

        The planner stores param values as the save_output_as key of the
        step that produced them (e.g. "scraped_products").  At execution
        time we swap those strings for whatever is in self.context under
        that key.  Non-string values and unknown keys are passed through
        unchanged.

        Example
        -------
        params = {"products": "scraped_products", "max_price": 200}
        context = {"scraped_products": [<Product>, ...]}
        → {"products": [<Product>, ...], "max_price": 200}
        """
        hydrated = {}
        for key, value in params.items():
            if isinstance(value, str) and value in self.context:
                hydrated[key] = self.context[value]
            else:
                hydrated[key] = value
        return hydrated

    # Tool executors  (receive params)

    def _execute_scraper(self, params: dict):
        """Keyword scraper — calls Blinkit spider and returns product list."""
        keywords     = params.get("keywords") or [self.context["query"]]
        fetch_details = params.get("fetch_details", True)

        # keywords from intent is a list like ["sugar free vanilla ice cream"]
        if isinstance(keywords, str):
            keywords = [keywords]

        products = self.scraper_tool.execute(
            keywords  = keywords,
            pincode   = self.context["pincode"],
            latitude  = self.context["latitude"],
            longitude = self.context["longitude"],
            fetch_details = fetch_details,
        )

        self.context["products_scraped"] = len(products)
        self.logger.info(f"Scraped {len(products)} products for: {keywords}")
        return products

    def _execute_price_filter(self, params: dict):
        """Keep only products within max_price budget."""
        products  = params.get("products") or []
        max_price = params.get("max_price")

        if not products:
            self.logger.warning("     price_filter received empty product list")
            return []

        if max_price is not None:
            filtered = [p for p in products if p.price <= float(max_price)]
            self.logger.info(
                f"     Price filter: {len(products)} → {len(filtered)} products (≤₹{max_price})"
            )
        else:
            filtered = products
            self.logger.info("     No max_price set — skipping price filter")

        self.context["products_filtered"] = len(filtered)
        return filtered

    def _execute_dietary_filter(self, params: dict):
        """Filter by dietary constraints (sugar_free, low_calorie, etc.)."""
        products    = params.get("products") or []
        constraints = params.get("constraints") or []

        if not products:
            self.logger.warning("     dietary_filter received empty product list")
            return []

        if not constraints:
            self.logger.info("     No dietary constraints — skipping filter")
            return products

        # constraints arrive as a list of dicts: [{"type": "sugar_free", "priority": "must_have"}]
        # normalise to plain strings for matching
        constraint_types = []
        for c in constraints:
            if isinstance(c, dict):
                constraint_types.append(c.get("type", "").lower())
            elif isinstance(c, str):
                constraint_types.append(c.lower())
            else:
                # Pydantic model with .type attribute
                constraint_types.append(getattr(c, "type", "").lower())

        # pass the raw intent dict directly — FilterTool should accept dicts
        intent = self.context["intent"]
        filtered = self.filter_tool.filter(products, intent)

        self.logger.info(
            f"     Dietary filter ({constraint_types}): "
            f"{len(products)} → {len(filtered)} products"
        )
        self.context["products_filtered"] = len(filtered)
        return filtered

    def _execute_flavour_filter(self, params: dict):
        """Keep products matching the requested flavour."""
        products = params.get("products") or []
        flavour  = params.get("flavour")

        if not products:
            self.logger.warning("     flavour_filter received empty product list")
            return []

        if flavour:
            filtered = [
                p for p in products
                if p.flavour and flavour.lower() in p.flavour.lower()
            ]
            self.logger.info(
                f"     Flavour filter ({flavour}): {len(products)} → {len(filtered)} products"
            )
        else:
            filtered = products
            self.logger.info("     No flavour specified — skipping filter")

        self.context["products_filtered"] = len(filtered)
        return filtered

    def _execute_brand_filter(self, params: dict):
        """Keep products from specified brands."""
        products = params.get("products") or []
        brands   = params.get("brands") or []

        if not products:
            self.logger.warning("     brand_filter received empty product list")
            return []

        if brands:
            brands_lower = [b.lower() for b in brands]
            filtered = [
                p for p in products
                if p.brand_name and any(b in p.brand_name.lower() for b in brands_lower)
            ]
            self.logger.info(
                f"     Brand filter ({brands}): {len(products)} → {len(filtered)} products"
            )
        else:
            filtered = products

        return filtered

    def _execute_nutrition_ranker(self, params: dict):
        """Rank products by nutritional score."""
        products = params.get("products") or []
        top_n    = params.get("top_n", 5)

        if not products:
            self.logger.warning("nutrition_ranker received empty product list")
            return []

        intent  = self.context["intent"]
        ranked  = self.ranker_tool.rank(products, intent, top_n=top_n)

        self.logger.info(f"Ranked {len(ranked)} products (nutrition)")
        return ranked

    def _execute_composite_ranker(self, params: dict):
        """Rank products by composite score (price + nutrition)."""
        products = params.get("products") or []
        top_n    = params.get("top_n", 5)

        if not products:
            self.logger.warning("     composite_ranker received empty product list")
            return []

        intent = self.context["intent"]
        ranked = self.ranker_tool.rank(products, intent, top_n=top_n)

        self.logger.info(f"     Ranked {len(ranked)} products (composite)")
        return ranked

    def _execute_response_generator(self, params= {}):
        """Format the final ranked list into a user-facing response."""
        ranked_products = self.context.get("ranked_products", [])
        intent          = self.context["intent"]
        query           = self.context["query"]

        if not ranked_products:
            self.logger.warning(
                "     response_generator: no ranked_products in context — "
                "trying flavour_products / dietary_products / scraped_products as fallback"
            )
            ranked_products = (
                self.context.get("flavour_products")
                or self.context.get("dietary_products")
                or self.context.get("scraped_products")
                or []
            )

        response = self.response_generator.generate(ranked_products, intent, query)
        return response