from fastapi import APIRouter, Query

from app.utils.egypt_address import (
    get_governorates,
    get_cities,
    get_areas_for_governorate,
    calculate_shipping,
    validate_egyptian_address,
)

router = APIRouter(prefix="/api/address", tags=["Egypt Address"])


@router.get("/governorates")
async def list_governorates():
    return get_governorates()


@router.get("/cities")
async def list_cities(governorate: str = Query(...)):
    return get_cities(governorate)


@router.get("/areas")
async def list_areas(governorate: str = Query(...)):
    return get_areas_for_governorate(governorate)


@router.get("/shipping")
async def shipping_cost(governorate: str = Query(...), subtotal: float = 0):
    # FIX: calculate_shipping returns a *dict* (cost/free/governorate/message/...)
    # — the old code wrapped it in float() and 500'd on every call.
    result = calculate_shipping(governorate, subtotal)
    payload = dict(result)
    payload["shipping_cost"] = float(payload.get("cost", 0))
    return payload


@router.get("/validate")
async def validate_address(governorate: str = Query(...), city: str = Query(None)):
    return {"valid": validate_egyptian_address(governorate, city)}
