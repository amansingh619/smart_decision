# pipeline.py (updated with Planner)

import time
import uuid
import logging
from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from spiders.blinkit_spider.keyword_page_spider import BlinkitSpider
from agents.intent_router import IntentRouter
from agents.planner import PlannerAgent, ExecutionPlan, PlanStep, StepStatus, ToolName
from agents.response_generator import ResponseGenerator
from tools.scraper_tool import ScraperTool
from tools.filter_tool import FilterTool
from tools.ranker_tool import RankerTool
from schemas.response import PipelineResult

class RecommendationPipeline:
    """
    Main orchestrator with Planner Agent
    """
    
    def __init__(self, spider_instance, logger):
        self.logger = logger
        
        # agents inst
        self.intent_router = IntentRouter(logger)
        self.planner = PlannerAgent()  
        self.response_generator = ResponseGenerator()
        
        # Initialize all tools
        self.scraper_tool = ScraperTool(spider_instance, logger)
        self.filter_tool = FilterTool()
        self.ranker_tool = RankerTool()
        
        # Tool registry - maps tool names to actual functions
        self.tool_registry = {
            ToolName.KEYWORD_SCRAPER: self._execute_scraper,
            ToolName.PRICE_FILTER: self._execute_price_filter,
            ToolName.DIETARY_FILTER: self._execute_dietary_filter,
            ToolName.FLAVOUR_FILTER: self._execute_flavour_filter,
            ToolName.BRAND_FILTER: self._execute_brand_filter,
            ToolName.NUTRITION_RANKER: self._execute_nutrition_ranker,
            ToolName.COMPOSITE_RANKER: self._execute_composite_ranker,
            ToolName.RESPONSE_GENERATOR: self._execute_response_generator,
        }
        
        # Context store - it will be holding the results for each step
        self.context: Dict[str, Any] = {}
        
    def launch_job(self, 
            query: str, 
            pincode: str = "302006",
            latitude: str = '26.9059311', 
            longitude: str = '75.78443829999999'
        ) -> PipelineResult:
        """
        launching the job
        """
        query_id = str(uuid.uuid4().hex)[:16]
        start_time = time.time()
        errors = []
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Pipeline Started | Query ID: {query_id}\n")
        self.logger.info(f"Query: '{query}'")
        self.logger.info(f"{'='*60}")
        
        # context updation
        self.context = {
            "query": query,
            "pincode": pincode,
            "latitude": latitude,
            "longitude": longitude
        }
        
        # Intent Classification
        self.logger.info("\nSTEP 1: Intent Classification...")
        intent = self.intent_router.classify_intent(query)
        self.logger.info(f"   Intent: {intent.primary_intent.value} (confidence: {intent.confidence})")
        self.context["intent"] = intent
        
        # ==========================================
        # STEP 2: Create Execution Plan
        # ==========================================
        self.logger.info("\n STEP 2: Creating Execution Plan...")
        plan = self.planner.create_plan(query, intent)
        
        self.logger.info(f"   Plan: {plan.plan_id}")
        self.logger.info(f"   Strategy: {self.planner.PLAN_TEMPLATES[intent.primary_intent]['description']}")
        self.logger.info(f"   Estimated time: {plan.estimated_time_seconds:.1f}s")
        self.logger.info(f"   Steps:")
        for step in plan.steps:
            self.logger.info(f"      {step.step_id}. [{step.tool.value}] {step.description}")
            self.logger.info(f"         Reason: {step.reasoning}")
            if step.depends_on:
                self.logger.info(f"         Depends on: {step.depends_on}")
        
        # ==========================================
        # STEP 3: Execute Plan
        # ==========================================
        self.logger.info("\n  STEP 3: Executing Plan...")
        self._execute_plan(plan, errors)
        
        # ==========================================
        # Build result
        # ==========================================
        execution_time = time.time() - start_time
        
        ranked_products = self.context.get("ranked_products", [])
        response_text = self.context.get("final_response", "No response generated")
        
        result = PipelineResult(
            query_id=query_id,
            original_query=query,
            pincode=pincode,
            intent=intent,
            products_scraped=self.context.get("products_scraped", 0),
            products_filtered=self.context.get("products_filtered", 0),
            ranked_products=ranked_products,
            response_text=response_text,
            execution_time_seconds=round(execution_time, 2),
            errors=errors,
            completed_at=datetime.now()
        )
        
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"Pipeline Complete | Time: {execution_time:.2f}s")
        self.logger.info(f"{'='*60}")
        print(f"\n{response_text}")
        
        return result
    
    def _execute_plan(self, plan: ExecutionPlan, errors: list):
        """Execute the plan step by step, respecting dependencies"""
        
        completed_steps = set()
        failed_steps = set()
        
        while True:
            # Get steps ready for execution (dependencies met)
            ready_steps = [
                step for step in plan.steps 
                if step.status == StepStatus.PENDING
                and all(dep in completed_steps for dep in step.depends_on)
            ]
            
            if not ready_steps:
                # Check if we're done or stuck
                if len(completed_steps) + len(failed_steps) >= len(plan.steps):
                    break
                else:
                    # Stuck - some dependencies can't be met
                    stuck_steps = [
                        step for step in plan.steps
                        if step.status == StepStatus.PENDING
                        and any(dep in failed_steps for dep in step.depends_on)
                    ]
                    for step in stuck_steps:
                        self.logger.warning(f"Step {step.step_id} stuck - dependency failed")
                        step.status = StepStatus.SKIPPED
                    break
            
            # Execute ready steps
            for step in ready_steps:
                self.logger.info(f"\n Step {step.step_id}: {step.description}")
                self.logger.info(f"      Tool: {step.tool.value}")
                
                step.status = StepStatus.IN_PROGRESS
                
                try:
                    # Execute the tool
                    executor = self.tool_registry.get(step.tool)
                    if executor:
                        result = executor(step.params)
                        
                        # Store result in context
                        self.context[step.save_output_as] = result
                        
                        step.status = StepStatus.COMPLETED
                        completed_steps.add(step.step_id)
                        self.logger.info(f"Completed: {step.save_output_as}")
                    else:
                        raise ValueError(f"No executor for tool: {step.tool}")
                        
                except Exception as e:
                    self.logger.error(f"Failed: {e}")
                    step.status = StepStatus.FAILED
                    failed_steps.add(step.step_id)
                    errors.append(f"Step {step.step_id} ({step.tool.value}): {str(e)}")
                    
                    # Try to adapt the plan
                    if step.retry_on_failure or step.fallback_step:
                        plan = self.planner.adapt_plan(plan, step.step_id, str(e), self.context)
    
    # ==========================================
    # Tool Executors
    # ==========================================
    
    def _execute_scraper(self, params: dict):
        """Execute keyword scraper tool"""
        keywords = params.get("keywords", [self.context["query"]])
        fetch_details = params.get("fetch_details", True)
        
        products = self.scraper_tool.execute(
            keywords=keywords,
            pincode=self.context["pincode"],
            latitude=self.context["latitude"],
            longitude=self.context["longitude"],
            fetch_details=fetch_details
        )
        
        self.context["products_scraped"] = len(products)
        return products
    
    def _execute_price_filter(self, params: dict):
        """Execute price filter tool"""
        products = params.get("products", [])
        max_price = params.get("max_price")
        
        if max_price:
            filtered = [p for p in products if p.price <= max_price]
            self.logger.info(f"      Price filter: {len(products)} → {len(filtered)} (≤₹{max_price})")
        else:
            filtered = products
        
        self.context["products_filtered"] = len(filtered)
        return filtered
    
    def _execute_dietary_filter(self, params: dict):
        """Execute dietary filter tool"""
        products = params.get("products", [])
        constraints = params.get("constraints", [])
        
        if constraints:
            # Use FilterTool for dietary filtering
            # Create a temporary intent with these constraints
            from schemas.intent import IntentOutput, IntentEntities, DietaryConstraint
            temp_intent = IntentOutput(
                primary_intent=self.context["intent"].primary_intent,
                entities=IntentEntities(
                    dietary_constraints=[
                        DietaryConstraint(type=c.type if hasattr(c, 'type') else c)
                        for c in constraints
                    ]
                )
            )
            filtered = self.filter_tool.filter(products, temp_intent)
        else:
            filtered = products
        
        self.context["products_filtered"] = len(filtered)
        return filtered
    
    def _execute_flavour_filter(self, params: dict):
        """Execute flavour filter"""
        products = params.get("products", [])
        flavour = params.get("flavour")
        
        if flavour:
            filtered = [p for p in products 
                       if p.flavour and flavour.lower() in p.flavour.lower()]
            self.logger.info(f"      Flavour filter: {len(products)} → {len(filtered)} ({flavour})")
        else:
            filtered = products
        
        self.context["products_filtered"] = len(filtered)
        return filtered
    
    def _execute_brand_filter(self, params: dict):
        """Execute brand filter"""
        products = params.get("products", [])
        brands = params.get("brands", [])
        
        if brands:
            filtered = [p for p in products 
                       if any(b.lower() in p.brand_name.lower() for b in brands)]
            self.logger.info(f"      Brand filter: {len(products)} → {len(filtered)} ({brands})")
        else:
            filtered = products
        
        return filtered
    
    def _execute_nutrition_ranker(self, params: dict):
        """Execute nutrition-based ranking"""
        products = params.get("products", [])
        criteria = params.get("criteria", "balanced")
        
        intent = self.context["intent"]
        ranked = self.ranker_tool.rank(products, intent, top_n=5)
        return ranked
    
    def _execute_composite_ranker(self, params: dict):
        """Execute composite (multi-factor) ranking"""
        products = params.get("products", [])
        
        intent = self.context["intent"]
        ranked = self.ranker_tool.rank(products, intent, top_n=5)
        return ranked
    
    def _execute_response_generator(self, params: dict):
        """Execute response generation"""
        ranked_products = self.context.get("ranked_products", [])
        intent = self.context["intent"]
        query = self.context["query"]
        
        response = self.response_generator.generate(ranked_products, intent, query)
        return response