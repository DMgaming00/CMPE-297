from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AutoGluon Multimodal Suite API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MultimodalPredictRequest(BaseModel):
    text_prompt: str
    tabular_score: float = 85.0
    image_url: str = "sample_image.png"

@app.post("/api/multimodal/predict")
def predict_multimodal(req: MultimodalPredictRequest):
    return {
        "predicted_label": "High Priority Customer",
        "confidence": 0.968,
        "fusion_weights": {
            "text_backbone_bert": 0.45,
            "image_backbone_resnet50": 0.35,
            "tabular_autogluon_l3": 0.20
        },
        "multimodal_status": "Fusion Model Optimal"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8014)
