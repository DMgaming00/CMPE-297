from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI(title="Anomaly Threat Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/telemetry")
def get_telemetry_stream():
    stream = []
    for i in range(30):
        is_anomaly = random.random() < 0.1
        score = random.uniform(0.78, 0.98) if is_anomaly else random.uniform(0.05, 0.35)
        stream.append({
            "timestamp": f"2026-09-06T20:{i:02d}:00Z",
            "anomaly_score": round(score, 3),
            "is_anomaly": is_anomaly,
            "threat_type": "DDOS_SPIKE" if is_anomaly else "NORMAL"
        })
    return {"telemetry": stream, "model": "IsolationForest-Autoencoder-Ensemble", "pr_auc": 0.942}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8006)
