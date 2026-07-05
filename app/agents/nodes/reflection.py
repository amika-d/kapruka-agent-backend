import json
import logging
from openai import AsyncOpenAI
from app.agents.state import GraphState
from app.core.config import settings
from app.core.prompt_loader import render_prompt

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=settings.openrouter_api_key,
    base_url="https://openrouter.ai/api/v1"
)

async def reflection_node(state: GraphState) -> dict:
    my_steps = []
    reflection_count = state.get("reflection_count", 0)
    search_results = state.get("search_results", [])
    
    if reflection_count >= 2:
        return {"reflection_needed": False, "reflection_count": reflection_count}

    # If no product search was requested or executed (e.g. delivery check or status query), pass immediately!
    if not state.get("refined_query") and not state.get("image_context") and not search_results:
        my_steps.append({
            "type": "thinking",
            "step": "Reflection",
            "detail": "Delivery/status check — no product search required.",
            "status": "done"
        })
        return {
            "reflection_needed": False,
            "reflection_count": reflection_count,
            "thinking_steps": my_steps
        }
        
    summary = ""
    if not search_results and reflection_count >= 1:
        my_steps.append({
            "type": "thinking",
            "step": "Reflection",
            "detail": "No results after retry — moving on.",
            "status": "done"
        })
        return {
            "reflection_needed": False,
            "reflection_count": reflection_count,
            "thinking_steps": my_steps
        }
    else:
        summary = "\n".join([f"- {r.get('name')} | Price: {r.get('price')} | Stock: {r.get('in_stock')}" for r in search_results])

    try:
        prompt_content = render_prompt(
            "reflection",
            search_results_summary=summary,
            original_intent=state.get("intent", "search"),
            budget_lkr=state.get("budget_lkr"),
            reflection_count=reflection_count
        )

        response = await client.chat.completions.create(
            model=settings.model_reflection,
            messages=[
                {"role": "user", "content": prompt_content}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        result = json.loads(content)
        
        reflection_needed = result.get("reflection_needed", False)
        reason = result.get("reason", "pass")
        
        if reflection_needed:
            my_steps.append({
                "type": "thinking",
                "step": "Reflection",
                "detail": f"Need better results because {reason}. Retrying...",
                "status": "done"
            })
        else:
            my_steps.append({
                "type": "thinking",
                "step": "Reflection",
                "detail": "Results look good.",
                "status": "done"
            })
            
        return {
            "reflection_needed": reflection_needed,
            "reflection_count": reflection_count + 1 if reflection_needed else reflection_count,
            "thinking_steps": my_steps
        }
    except Exception as e:
        logger.error(f"Reflection error: {e}")
        return {
            "reflection_needed": False,
            "reflection_count": reflection_count,
            "thinking_steps": my_steps
        }
