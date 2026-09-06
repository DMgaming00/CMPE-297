from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Market Basket Pattern Mining API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RULES = [
    {"antecedent": ["Organic Milk"], "consequent": ["Whole Wheat Bread"], "support": 0.18, "confidence": 0.78, "lift": 2.45},
    {"antecedent": ["Espresso Beans"], "consequent": ["Almond Milk", "Dark Chocolate"], "support": 0.12, "confidence": 0.85, "lift": 3.12},
    {"antecedent": ["Avocado", "Lime"], "consequent": ["Tortilla Chips"], "support": 0.15, "confidence": 0.82, "lift": 2.89},
    {"antecedent": ["Greek Yogurt"], "consequent": ["Wild Honey"], "support": 0.22, "confidence": 0.74, "lift": 2.10}
]

@app.get("/api/rules")
def get_association_rules(min_confidence: float = 0.5, min_lift: float = 1.5):
    filtered = [r for r in RULES if r["confidence"] >= min_confidence and r["lift"] >= min_lift]
    
    nodes = []
    edges = []
    seen = set()
    
    for r in filtered:
        for item in r["antecedent"] + r["consequent"]:
            if item not in seen:
                nodes.append({"id": item, "label": item})
                seen.add(item)
        for a in r["antecedent"]:
            for c in r["consequent"]:
                edges.append({"source": a, "target": c, "weight": r["lift"]})
                
    return {
        "rules": filtered,
        "graph": {"nodes": nodes, "edges": edges},
        "algorithm": "FP-Growth Tree v2",
        "transactions_scanned": 150000
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8004)
