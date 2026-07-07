import httpx
from fastapi import APIRouter, Depends, HTTPException

from app import db, nim_client
from app.auth import current_user
from app.models import ModelMappingIn, ModelMappingOut

router = APIRouter(prefix="/api/models", tags=["models"])

# Substrings that indicate a non-chat model — filtered out of the picker.
_NON_CHAT_SUBSTRINGS = (
    "embed",
    "embedding",
    "rerank",
    "reranking",
    "guard",
    "safety",
    "-parse",
    "ocr",
    "retriever",
    "reward",
)


def _is_chat_model(model_id: str) -> bool:
    low = model_id.lower()
    return not any(s in low for s in _NON_CHAT_SUBSTRINGS)


@router.get("/nim")
async def list_nim_models(_: dict = Depends(current_user)):
    try:
        models = await nim_client.list_models()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Failed to reach NVIDIA NIM: {e}")
    chat = sorted(
        [m["id"] for m in models if _is_chat_model(m.get("id", ""))]
    )
    return {"models": chat, "total": len(models), "chat_count": len(chat)}


@router.post("/test")
async def test_model(body: dict, _: dict = Depends(current_user)):
    """Fire a tiny probe completion to check whether a model is runnable."""
    model = (body or {}).get("model", "")
    if not model:
        raise HTTPException(400, "model is required")
    return await nim_client.probe(model)


@router.get("/mappings", response_model=list[ModelMappingOut])
async def get_mappings(_: dict = Depends(current_user)):
    out = []
    async for m in db.model_mappings().find():
        out.append(ModelMappingOut(slot=m["slot"], nim_model=m["nim_model"]))
    return out


@router.put("/mappings", response_model=ModelMappingOut)
async def set_mapping(body: ModelMappingIn, _: dict = Depends(current_user)):
    await db.model_mappings().update_one(
        {"slot": body.slot},
        {"$set": {"slot": body.slot, "nim_model": body.nim_model}},
        upsert=True,
    )
    return ModelMappingOut(slot=body.slot, nim_model=body.nim_model)
