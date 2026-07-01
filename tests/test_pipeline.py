"""
Quick pipeline test — runs all 4 intent scenarios against the live backend.
Usage: uv run python tests/test_pipeline.py
Backend must be running: uv run uvicorn app.main:app
"""
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/api/v1/chat"

SCENARIOS = [
    {
        "name": "🔍 Search",
        "session_id": "pipe-test-search",
        "message": "Show me birthday cakes under 3000 LKR"
    },
    {
        "name": "📦 Track Order",
        "session_id": "pipe-test-track",
        "message": "Where is my order VPAY827982BA?"
    },
    {
        "name": "🛒 Checkout (empty cart)",
        "session_id": "pipe-test-checkout",
        "message": "I want to buy these and deliver to Colombo"
    },
    {
        "name": "👋 Greeting",
        "session_id": "pipe-test-greet",
        "message": "Hello Kiyanna!"
    },
]


async def run_scenario(client: httpx.AsyncClient, scenario: dict):
    print(f"\n{'='*60}")
    print(f"  {scenario['name']}")
    print(f"  Message: \"{scenario['message']}\"")
    print(f"{'='*60}")

    payload = {
        "session_id": scenario["session_id"],
        "message": scenario["message"],  # ChatRequest expects `message: str`
        "history": [],
        "cart": []
    }

    intent_found = None
    text_chunks = []
    ui_events = []
    thinking_steps = []

    async with client.stream("POST", BASE_URL, json=payload, timeout=60.0) as response:
        if response.status_code != 200:
            print(f"  ❌ HTTP {response.status_code}")
            return

        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if raw == "[DONE]":
                break
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            dtype = data.get("type")
            if dtype == "thinking":
                step = data.get("step", "")
                detail = data.get("detail", "")
                if step == "Routing":
                    intent_found = detail
                thinking_steps.append(f"  🧠 [{step}] {detail}")
            elif dtype == "text":
                text_chunks.append(data.get("content", ""))
            elif dtype in ("tracking_card", "pay_link", "ui"):
                ui_events.append(dtype)

    print(f"\n  Routing: {intent_found or 'unknown'}")
    print(f"\n  Thinking steps:")
    for s in thinking_steps:
        print(s)

    full_text = "".join(text_chunks).strip()
    if full_text:
        preview = full_text[:300] + ("..." if len(full_text) > 300 else "")
        print(f"\n  Concierge response:\n  {preview}")

    if ui_events:
        print(f"\n  UI events emitted: {ui_events}")

    print(f"\n  ✅ Done\n")


async def main():
    print("\n🚀 Kiyanna Pipeline Test")
    print("  Backend:", BASE_URL)

    async with httpx.AsyncClient() as client:
        # Health check first
        try:
            r = await client.get("http://localhost:8000/api/v1/health", timeout=5.0)
            print(f"  Health: {r.status_code} {r.json()}")
        except Exception as e:
            print(f"  ❌ Backend not reachable: {e}")
            return

        for scenario in SCENARIOS:
            try:
                await run_scenario(client, scenario)
            except Exception as e:
                print(f"  ❌ Error in {scenario['name']}: {e}")
            await asyncio.sleep(1)  # small gap between calls


if __name__ == "__main__":
    asyncio.run(main())
