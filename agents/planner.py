# agents/planner.py

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from schemas.intent import IntentOutput, QueryIntent


class ToolName(str, Enum):
    """Available tools the planner can use"""
    KEYWORD_SCRAPER = "keyword_scraper"
    PRODUCT_DETAIL_SCRAPER = "product_detail_scraper"
    PRICE_FILTER = "price_filter"
    DIETARY_FILTER = "dietary_filter"
    FLAVOUR_FILTER = "flavour_filter"
    BRAND_FILTER = "brand_filter"
    NUTRITION_RANKER = "nutrition_ranker"
    PRICE_RANKER = "price_ranker"
    COMPOSITE_RANKER = "composite_ranker"
    COMPARISON_ENGINE = "comparison_engine"
    RESPONSE_GENERATOR = "response_generator"

class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class PlanStep(BaseModel):
    """Single step in the execution plan"""
    step_id: int
    tool: ToolName
    description: str  # Human-readable description of what this step does
    params: Dict[str, Any] = Field(default_factory=dict)  # Parameters for the tool
    depends_on: List[int] = Field(default_factory=list)  # Steps that must complete first
    save_output_as: str  # Variable name to store output
    retry_on_failure: bool = False
    max_retries: int = 1
    fallback_step: Optional[int] = None  # Alternative step if this fails
    status: StepStatus = StepStatus.PENDING
    reasoning: str = ""  # Why this step is needed

class ExecutionPlan(BaseModel):
    """Complete execution plan"""
    plan_id: str
    query: str
    intent: IntentOutput
    steps: List[PlanStep]
    estimated_time_seconds: float = 0.0
    total_steps: int = 0
    requires_scraping: bool = False
    requires_ranking: bool = False
    
    def get_pending_steps(self) -> List[PlanStep]:
        """Get steps that are ready to execute (dependencies met)"""
        completed_ids = {
            step.step_id 
            for step in self.steps 
            if step.status == StepStatus.COMPLETED
        }
        
        pending = []
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                # Check if all dependencies are completed
                if all(dep in completed_ids for dep in step.depends_on):
                    pending.append(step)
        return pending

class PlannerAgent:
    """
    THE BRAIN: Converts intent into an executable plan.
    
    This is where the "reasoning" happens:
    - For recommendation queries → scrape keywords → filter → rank
    - For comparison queries → scrape specific products → compare
    - For budget queries → scrape → price filter → rank by value
    - For goal-based queries → scrape → dietary filter → health rank
    
    The Planner understands the available tools and creates optimal
    execution sequences based on user intent.
    """
    
    # Plan templates for different intent types
    PLAN_TEMPLATES = {
        QueryIntent.RECOMMENDATION: {
            "description": "Standard recommendation flow: scrape → filter → rank → respond",
            "steps": [
                {
                    "tool": ToolName.KEYWORD_SCRAPER,
                    "description": "Scrape products using derived keywords",
                    "save_as": "scraped_products",
                    "params_template": {
                        "keywords": "{{intent.suggested_keywords}}",
                        "fetch_details": True
                    }
                },
                {
                    "tool": ToolName.NUTRITION_RANKER,
                    "description": "Rank products by nutritional value",
                    "save_as": "ranked_products",
                    "depends_on": [1],
                    "params_template": {
                        "products": "{{scraped_products}}",
                        "criteria": "balanced"
                    }
                },
                {
                    "tool": ToolName.RESPONSE_GENERATOR,
                    "description": "Generate user-friendly response",
                    "save_as": "final_response",
                    "depends_on": [2],
                    "params_template": {}
                }
            ]
        },
        
        QueryIntent.BUDGET: {
            "description": "Budget-constrained flow: scrape → price filter → value ranking",
            "steps": [
                {
                    "tool": ToolName.KEYWORD_SCRAPER,
                    "description": "Scrape products with price-conscious keywords",
                    "save_as": "scraped_products",
                    "params_template": {
                        "keywords": "{{intent.suggested_keywords}}",
                        "fetch_details": True
                    }
                },
                {
                    "tool": ToolName.PRICE_FILTER,
                    "description": "Filter products within budget",
                    "save_as": "budget_products",
                    "depends_on": [1],
                    "params_template": {
                        "products": "{{scraped_products}}",
                        "max_price": "{{intent.entities.max_price}}"
                    },
                    "retry_on_failure": True,
                    "fallback_step": 3  # Skip to ranking if no products in budget
                },
                {
                    "tool": ToolName.COMPOSITE_RANKER,
                    "description": "Rank by value (price-to-quality ratio)",
                    "save_as": "ranked_products",
                    "depends_on": [2],
                    "params_template": {
                        "products": "{{budget_products}}",
                        "criteria": "value_for_money",
                        "max_price": "{{intent.entities.max_price}}"
                    }
                },
                {
                    "tool": ToolName.RESPONSE_GENERATOR,
                    "description": "Generate budget-aware response",
                    "save_as": "final_response",
                    "depends_on": [3],
                    "params_template": {
                        "include_budget_alternatives": True
                    }
                }
            ]
        },
        
        QueryIntent.GOAL_BASED: {
            "description": "Health-goal flow: scrape → dietary filter → health ranking",
            "steps": [
                {
                    "tool": ToolName.KEYWORD_SCRAPER,
                    "description": "Scrape products matching health goal",
                    "save_as": "scraped_products",
                    "params_template": {
                        "keywords": "{{intent.suggested_keywords}}",
                        "fetch_details": True
                    }
                },
                {
                    "tool": ToolName.DIETARY_FILTER,
                    "description": "Filter by dietary constraints (sugar free, low cal, etc.)",
                    "save_as": "dietary_products",
                    "depends_on": [1],
                    "params_template": {
                        "products": "{{scraped_products}}",
                        "constraints": "{{intent.entities.dietary_constraints}}"
                    },
                    "retry_on_failure": True,
                    "reasoning": "Must match dietary requirements strictly"
                },
                {
                    "tool": ToolName.FLAVOUR_FILTER,
                    "description": "Apply flavour preference if specified",
                    "save_as": "flavour_products",
                    "depends_on": [2],
                    "params_template": {
                        "products": "{{dietary_products}}",
                        "flavour": "{{intent.entities.flavour}}"
                    },
                    "condition": "intent.entities.flavour is not None"
                },
                {
                    "tool": ToolName.NUTRITION_RANKER,
                    "description": "Rank by health metrics",
                    "save_as": "ranked_products",
                    "depends_on": [3],
                    "params_template": {
                        "products": "{{flavour_products}}",
                        "criteria": "{{intent.primary_intent}}",
                        "dietary_constraints": "{{intent.entities.dietary_constraints}}"
                    }
                },
                {
                    "tool": ToolName.RESPONSE_GENERATOR,
                    "description": "Generate health-focused response",
                    "save_as": "final_response",
                    "depends_on": [4],
                    "params_template": {
                        "include_health_analysis": True
                    }
                }
            ]
        },
        
        QueryIntent.COMPARISON: {
            "description": "Comparison flow: scrape specific products → compare → respond",
            "steps": [
                {
                    "tool": ToolName.KEYWORD_SCRAPER,
                    "description": "Search for products to compare",
                    "save_as": "scraped_products",
                    "params_template": {
                        "keywords": "{{intent.suggested_keywords}}",
                        "fetch_details": True
                    }
                },
                {
                    "tool": ToolName.BRAND_FILTER,
                    "description": "Filter to only compared brands",
                    "save_as": "comparison_products",
                    "depends_on": [1],
                    "params_template": {
                        "products": "{{scraped_products}}",
                        "brands": "{{intent.entities.comparison_targets}}"
                    }
                },
                {
                    "tool": ToolName.COMPARISON_ENGINE,
                    "description": "Generate head-to-head comparison",
                    "save_as": "comparison_result",
                    "depends_on": [2],
                    "params_template": {
                        "products": "{{comparison_products}}",
                        "aspects": ["nutrition", "price", "value", "ingredients"]
                    }
                },
                {
                    "tool": ToolName.RESPONSE_GENERATOR,
                    "description": "Generate comparison response",
                    "save_as": "final_response",
                    "depends_on": [3],
                    "params_template": {
                        "format": "comparison_table"
                    }
                }
            ]
        }
    }
    
    def create_plan(self, query: str, intent: IntentOutput, 
                    available_tools: Optional[List[ToolName]] = None) -> ExecutionPlan:
        """
        Create execution plan based on intent.
        This is the core reasoning engine.
        """
        
        # Get template for this intent type
        template = self.PLAN_TEMPLATES.get(intent.primary_intent)
        
        if not template:
            # Fallback to recommendation template
            template = self.PLAN_TEMPLATES[QueryIntent.RECOMMENDATION]
        
        # Build plan steps from template
        steps = []
        step_id = 0
        
        for step_template in template["steps"]:
            step_id += 1
            
            # Check if this step has a condition
            condition = step_template.get("condition")
            if condition and not self._evaluate_condition(condition, intent):
                continue  # Skip optional steps that don't apply
            
            # Resolve parameters
            resolved_params = self._resolve_params(
                step_template.get("params_template", {}), 
                intent
            )
            
            # Determine dependencies
            depends_on = step_template.get("depends_on", [])
            
            # Handle fallback
            fallback = step_template.get("fallback_step")
            
            # Add reasoning
            reasoning = step_template.get("reasoning", self._generate_reasoning(
                step_template["tool"], intent, step_id
            ))
            
            step = PlanStep(
                step_id=step_id,
                tool=step_template["tool"],
                description=step_template["description"],
                params=resolved_params,
                depends_on=depends_on,
                save_output_as=step_template["save_as"],
                retry_on_failure=step_template.get("retry_on_failure", False),
                max_retries=step_template.get("max_retries", 1),
                fallback_step=fallback,
                reasoning=reasoning
            )
            
            # Check tool availability
            if available_tools and step.tool not in available_tools:
                step.status = StepStatus.SKIPPED
                step.reasoning += " (Tool unavailable, skipping)"
            
            steps.append(step)
        
        # Estimate time
        estimated_time = self._estimate_execution_time(steps)
        
        plan = ExecutionPlan(
            plan_id=f"plan_{intent.primary_intent.value}_{hash(query) % 10000}",
            query=query,
            intent=intent,
            steps=steps,
            estimated_time_seconds=estimated_time,
            total_steps=len(steps),
            requires_scraping=any(s.tool == ToolName.KEYWORD_SCRAPER for s in steps),
            requires_ranking=any(s.tool in [ToolName.NUTRITION_RANKER, ToolName.COMPOSITE_RANKER] for s in steps)
        )
        
        return plan
    
    def _resolve_params(self, template: Dict, intent: IntentOutput) -> Dict:
        """Resolve template parameters with actual intent values"""
        resolved = {}
        
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                # Template variable - resolve from intent
                path = value[2:-2].strip()
                resolved[key] = self._get_nested_value(intent, path)
            else:
                resolved[key] = value
        
        return resolved
    
    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """Get nested attribute from object using dot notation"""
        parts = path.split(".")
        current = obj
        
        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    def _evaluate_condition(self, condition: str, intent: IntentOutput) -> bool:
        """Evaluate a condition string against the intent"""
        try:
            # Simple condition evaluator
            # Supports: "intent.entities.flavour is not None"
            parts = condition.split(" is ")
            value = self._get_nested_value(intent, parts[0].strip())
            
            if "not None" in parts[1]:
                return value is not None
            elif "None" in parts[1]:
                return value is None
            
            return False
        except:
            return True  # Default to including step if condition can't be evaluated
    
    def _generate_reasoning(self, tool: ToolName, intent: IntentOutput, step_id: int) -> str:
        """Generate human-readable reasoning for why this step is needed"""
        reasoning_map = {
            ToolName.KEYWORD_SCRAPER: f"Need to find products matching '{intent.primary_intent.value}' intent using keywords: {intent.suggested_keywords}",
            ToolName.PRICE_FILTER: f"User has budget constraint of ₹{intent.entities.max_price} - filtering is essential",
            ToolName.DIETARY_FILTER: f"User requires specific dietary compliance: {[c.type for c in intent.entities.dietary_constraints]}",
            ToolName.FLAVOUR_FILTER: f"User specified flavour preference: {intent.entities.flavour}",
            ToolName.NUTRITION_RANKER: "Ranking by nutritional value aligns with health-conscious query",
            ToolName.COMPOSITE_RANKER: "Multi-factor ranking needed for balanced recommendation",
            ToolName.COMPARISON_ENGINE: "Head-to-head comparison required for 'compare' intent",
            ToolName.RESPONSE_GENERATOR: "Final step: format results as user-friendly response"
        }
        return reasoning_map.get(tool, f"Step {step_id}: {tool.value}")
    
    def _estimate_execution_time(self, steps: List[PlanStep]) -> float:
        """Estimate total execution time"""
        time_estimates = {
            ToolName.KEYWORD_SCRAPER: 15.0,  # Scraping takes longest
            ToolName.PRODUCT_DETAIL_SCRAPER: 10.0,
            ToolName.PRICE_FILTER: 0.5,
            ToolName.DIETARY_FILTER: 0.5,
            ToolName.FLAVOUR_FILTER: 0.3,
            ToolName.BRAND_FILTER: 0.3,
            ToolName.NUTRITION_RANKER: 1.0,
            ToolName.COMPOSITE_RANKER: 1.0,
            ToolName.COMPARISON_ENGINE: 2.0,
            ToolName.RESPONSE_GENERATOR: 2.0,
        }
        
        # Account for parallel execution (steps without dependencies can run in parallel)
        sequential_time = sum(time_estimates.get(s.tool, 1.0) for s in steps)
        
        # Simple parallel estimation: if no dependencies, can run in parallel
        parallel_groups = {}
        for step in steps:
            if not step.depends_on:
                group = 0
            else:
                group = max(step.depends_on)
            if group not in parallel_groups:
                parallel_groups[group] = []
            parallel_groups[group].append(step)
        
        # Max time per group
        parallel_time = sum(
            max(time_estimates.get(s.tool, 1.0) for s in group_steps)
            for group_steps in parallel_groups.values()
        )
        
        return min(sequential_time, parallel_time)  # Best case with parallelization
    
    def adapt_plan(self, plan: ExecutionPlan, step_id: int, 
                   error: str, context: Dict[str, Any]) -> ExecutionPlan:
        """
        Adapt the plan when a step fails.
        This is where the planner gets "smart" - it can change strategy.
        """
        
        # Find the failed step
        for step in plan.steps:
            if step.step_id == step_id:
                step.status = StepStatus.FAILED
                
                # Check if we have a fallback
                if step.fallback_step:
                    print(f"Step {step_id} failed, using fallback step {step.fallback_step}")
                    # Activate fallback step
                    for s in plan.steps:
                        if s.step_id == step.fallback_step:
                            s.status = StepStatus.PENDING
                            # Remove dependency on failed step
                            s.depends_on = [d for d in s.depends_on if d != step_id]
                            if not s.depends_on:
                                # If no dependencies left, execute immediately
                                s.reasoning += f" (Activated as fallback for failed step {step_id})"
                
                # If keyword scraper failed with no results, try broader keywords
                if step.tool == ToolName.KEYWORD_SCRAPER and step.retry_on_failure:
                    if step.max_retries > 0:
                        print(f" Retrying step {step_id} with broader keywords...")
                        # Broaden the keywords
                        original_keywords = step.params.get("keywords", [])
                        broader_keywords = self._broaden_keywords(original_keywords)
                        step.params["keywords"] = broader_keywords
                        step.max_retries -= 1
                        step.status = StepStatus.PENDING
                        step.reasoning += f" | Retrying with broader keywords: {broader_keywords}"
                
                break
        
        return plan
    
    def _broaden_keywords(self, keywords: List[str]) -> List[str]:
        """Broaden search keywords when initial search fails"""
        broader = []
        for kw in keywords:
            # Remove specific constraints
            broader_kw = kw.replace("sugar free ", "").replace("low calorie ", "")
            broader_kw = broader_kw.replace("vanilla ", "").replace("chocolate ", "")
            
            # If too short, use generic
            if len(broader_kw.split()) < 2:
                broader_kw = "ice cream"
            
            broader.append(broader_kw.strip())
        
        return list(set(broader))  # Deduplicate