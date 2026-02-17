from __future__ import annotations

from fastapi import APIRouter

from rawl.api.schemas.pretrained import PretrainedModelResponse

router = APIRouter(tags=["pretrained"])

# Hardcoded registry — keys map to fixed S3 paths, never constructed from user input.
PRETRAINED_MODELS: dict[str, dict] = {
    "sf2ce-linyilyi-2500k": {
        "game_id": "sf2ce",
        "name": "LinyiLYi 2500k",
        "character": "Ryu",
        "description": "Community baseline trained on SF2 Champion Edition (2.5M steps, PPO)",
        "s3_key": "pretrained/sf2ce/linyiLYi_2500k.zip",
    },
    "sf2ce-thuongmhh-discrete15": {
        "game_id": "sf2ce",
        "name": "ThuongMHH Discrete15",
        "character": "Ryu",
        "description": "Community baseline trained on SF2 Champion Edition (discrete action space)",
        "s3_key": "pretrained/sf2ce/thuongmhh_discrete15.zip",
    },
}


@router.get("/pretrained", response_model=list[PretrainedModelResponse])
async def list_pretrained():
    """List available pretrained models that users can adopt as fighters."""
    return [
        PretrainedModelResponse(id=model_id, **{k: v for k, v in info.items() if k != "s3_key"})
        for model_id, info in PRETRAINED_MODELS.items()
    ]
