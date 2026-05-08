# backend/app/api/llm_pricing.py
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.llm_pricing import PRICING

router = APIRouter()


class ModelPricing(BaseModel):
    input_per_mtoken: float
    output_per_mtoken: float


@router.get("/llm/pricing", response_model=dict[str, ModelPricing])
def get_llm_pricing() -> dict[str, ModelPricing]:
    return {
        model: ModelPricing(input_per_mtoken=inp, output_per_mtoken=out)
        for model, (inp, out) in PRICING.items()
    }
