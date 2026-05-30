# smart_decision

This Repo holds all the projects around AI agents

plan_id='plan_recommendation_72719479'
query='Best sugar free vanilla ice cream under 200'
intent={
    'primary_intent': 'recommendation', 
    'secondary_intents': ['budget', 'goal_based'], 
    'entities': {
        'flavour': 'vanilla', 
        'brand': None, 
        'dietary_constraints': [
            {
                'type': 'sugar_free', 
                'priority': 'must_have'
            }
        ], 
        'max_price': 200, 
        'min_price': None, 
        'pack_type': None, 
        'sort_preference': None
    }, 
    'confidence': 0.95, 
    'requires_scraping': True, 
    'requires_detail_scraping': True, 
    'suggested_keywords': ['sugar free vanilla ice cream'], 
    'clarification_question': None
    } 
steps=[
    PlanStep(
        step_id=1, 
        tool=<ToolName.KEYWORD_SCRAPER: 'keyword_scraper'>, 
        description='Scrape products using suggested keywords', 
        params={
            'keywords': ['sugar free vanilla ice cream'], 
            'fetch_details': True
        }, 
        depends_on=[], 
        save_output_as='scraped_products', 
        retry_on_failure=False, 
        max_retries=1, 
        fallback_step=None, 
        status=<StepStatus.PENDING: 'pending'>, 
        reasoning="Find products for 'recommendation' using: ['sugar free vanilla ice cream']"
    ), 
    PlanStep(
        step_id=2, 
        tool=<ToolName.NUTRITION_RANKER: 'nutrition_ranker'>, 
        description='Rank by nutritional value', 
        params={
            'criteria': 'balanced'
        }, 
        depends_on=[1], 
        save_output_as='ranked_products', 
        retry_on_failure=False, 
        max_retries=1, 
        fallback_step=None, 
        status=<StepStatus.PENDING: 'pending'>, 
        reasoning='Rank by nutritional value — aligns with health query'
    ), 
    PlanStep(
        step_id=3, 
        tool=<ToolName.RESPONSE_GENERATOR: 'response_generator'>, 
        description='Format results for the user', 
        params={}, 
        depends_on=[2], 
        save_output_as='final_response', 
        retry_on_failure=False, 
        max_retries=1, 
        fallback_step=None, 
        status=<StepStatus.PENDING: 'pending'>, 
        reasoning='Final step — format results for user'
    )
    ] 
created_at='2026-05-28T11:25:57.196586+00:00' 
estimated_time_s=13.0 
total_steps=3 
requires_scraping=True 
requires_ranking=True
