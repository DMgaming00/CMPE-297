from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import random

app = FastAPI(title="Customer Intelligence Clustering API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/clusters")
def get_customer_clusters(n_clusters: int = 4):
    clusters_info = [
        {"id": 0, "name": "VIP Champions", "size": 320, "avg_recency": 12, "avg_frequency": 45, "avg_monetary": 4200},
        {"id": 1, "name": "Loyal Regulars", "size": 650, "avg_recency": 28, "avg_frequency": 18, "avg_monetary": 1450},
        {"id": 2, "name": "At-Risk Bargain Seekers", "size": 410, "avg_recency": 110, "avg_frequency": 5, "avg_monetary": 380},
        {"id": 3, "name": "New High Potentials", "size": 220, "avg_recency": 8, "avg_frequency": 3, "avg_monetary": 950}
    ]
    
    points = []
    for c in clusters_info[:n_clusters]:
        for _ in range(25):
            points.append({
                "x": round(random.gauss(c["id"] * 3.5, 0.8), 2),
                "y": round(random.gauss(c["avg_frequency"] * 0.1, 0.9), 2),
                "z": round(random.gauss(c["avg_monetary"] * 0.001, 0.7), 2),
                "cluster": c["name"]
            })
            
    return {
        "clusters": clusters_info[:n_clusters],
        "points_3d": points,
        "silhouette_score": 0.642,
        "inertia": 1245.8,
        "optimal_k": 4
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8003)
