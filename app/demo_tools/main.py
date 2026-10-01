import os
from hashlib import sha256
from typing import Any

from fastapi import FastAPI, Header, HTTPException

KIND = os.getenv("TOOL_KIND", "unknown")
app = FastAPI(title=f"Demo tool: {KIND}")

RATES = {"USD": 1.0, "EUR": 1.1, "INR": 0.012}
ARTICLES = (
    {"id": "kb-1", "title": "Reset a demo account", "text": "Ask the local administrator for a new demo token."},
    {"id": "kb-2", "title": "Tool gateway", "text": "Tools need role permission before invocation."},
    {"id": "kb-3", "title": "Rate limits", "text": "Demo calls have a per user and tool limit."},
)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/invoke")
def invoke(payload: dict[str, Any], x_request_id: str = Header(default="")) -> dict[str, Any]:
    if KIND == "currency":
        amount = float(payload["amount"])
        source = str(payload["from_currency"])
        target = str(payload["to_currency"])
        converted = round(amount * RATES[source] / RATES[target], 2)
        return {"amount": converted, "currency": target, "rate_source": "fixed-demo-rates"}
    if KIND == "knowledge":
        query = str(payload["query"]).casefold()
        matches = [{"id": item["id"], "title": item["title"]} for item in ARTICLES if query in (item["title"] + " " + item["text"]).casefold()]
        return {"results": matches[:10]}
    if KIND == "ticket":
        ticket_id = sha256(x_request_id.encode()).hexdigest()[:12]
        return {"ticket_id": f"demo-{ticket_id}", "status": "simulated", "category": payload["category"]}
    raise HTTPException(status_code=404, detail="Unknown demo tool")

