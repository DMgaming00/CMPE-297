from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import math

app = FastAPI(title="DS Visual Foundations API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/distributions/normal")
def normal_distribution(mean: float = 0.0, std: float = 1.0):
    points = []
    x = -4.0
    while x <= 4.0:
        pdf = (1.0 / (std * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((x - mean) / std) ** 2)
        points.append({"x": round(x, 2), "pdf": round(pdf, 4)})
        x += 0.2
    return {"mean": mean, "std": std, "points": points}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8008)
