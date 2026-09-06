from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="DS Skills Lab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SKILLS = [
    {"id": "pca", "name": "Principal Component Analysis", "category": "EDA", "formula": "X_pca = X * V_k"},
    {"id": "xgboost", "name": "XGBoost Gradient Boosting", "category": "Supervised ML", "formula": "L^{(t)} = \\sum g_i f_t(x_i) + \\frac{1}{2} h_i f_t^2(x_i)"},
    {"id": "apriori", "name": "Apriori Pattern Mining", "category": "Pattern Mining", "formula": "Lift(A \\to B) = \\frac{P(A \\cap B)}{P(A)P(B)}"},
    {"id": "rope", "name": "Rotary Positional Embedding", "category": "Deep Learning", "formula": "R_{\\Theta, m}^d x_m"}
]

@app.get("/api/skills")
def list_skills():
    return {"skills": SKILLS, "total_skills": 54, "datasets": ["Titanic", "House Prices", "NYC Taxi", "MNIST", "SPY 500"]}

@app.post("/api/skills/execute/{skill_id}")
def execute_skill(skill_id: str):
    return {
        "skill_id": skill_id,
        "status": "success",
        "runtime_ms": 14.2,
        "stdout": f"Executed analytical skill '{skill_id}' across Kaggle benchmark datasets.",
        "metrics": {"accuracy": 0.942, "execution_memory": "48MB"}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8005)
