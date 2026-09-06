from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AutoGluon Stacking AutoML API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LEADERBOARD = [
    {"model": "WeightedEnsemble_L3", "score_val": 0.945, "fit_time_s": 42.1, "stack_level": 3},
    {"model": "LightGBM_L2", "score_val": 0.932, "fit_time_s": 18.4, "stack_level": 2},
    {"model": "CatBoost_L2", "score_val": 0.929, "fit_time_s": 24.0, "stack_level": 2},
    {"model": "XGBoost_L1", "score_val": 0.910, "fit_time_s": 12.1, "stack_level": 1},
    {"model": "RandomForest_L1", "score_val": 0.885, "fit_time_s": 8.5, "stack_level": 1}
]

@app.get("/api/leaderboard")
def get_automl_leaderboard():
    return {
        "leaderboard": LEADERBOARD,
        "best_model": "WeightedEnsemble_L3",
        "stacking_levels": 3,
        "evaluation_metric": "roc_auc"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8007)
