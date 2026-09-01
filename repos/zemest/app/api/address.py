from fastapi import APIRouter, HTTPException, Query

from app.utils.egypt_address import (
    get_governorates,
    get_cities,
    get_areas_for_governorate,
    calculate_shipping,
    normalize_governorate,
    validate_egyptian_address,
)

router = APIRouter(prefix="/api/address", tags=["Egypt Address"])


def _canonical_or_404(governorate: str) -> str:
    """Canonicalize any spelling of a governorate; 404 on unknown input.

    The old exact-match lookup silently fell back to the outside-Cairo
    shipping rate (60 EGP) for any miss — 'Cairo', 'Port Said' and every
    Arabic-with-hamza-variant mischarged real customers. Unknown values
    must be an explicit error, never a silent price."""
    key = normalize_governorate(governorate)
    if not key:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown governorate: '{governorate}'. "
                "See /api/address/governorates for the full list."
            ),
        )
    return key


@router.get("/governorates")
async def list_governorates():
    return get_governorates()


@router.get("/cities")
async def list_cities(governorate: str = Query(...)):
    return get_cities(_canonical_or_404(governorate))


@router.get("/areas")
async def list_areas(governorate: str = Query(...)):
    return get_areas_for_governorate(_canonical_or_404(governorate))


@router.get("/shipping")
async def shipping_cost(governorate: str = Query(...), subtotal: float = 0):
    key = _canonical_or_404(governorate)
    # FIX: calculate_shipping returns a *dict* (cost/free/governorate/message/...)
    # — the old code wrapped it in float() and 500'd on every call.
    result = calculate_shipping(key, subtotal)
    payload = dict(result)
    payload["shipping_cost"] = float(payload.get("cost", 0))
    payload["governorate"] = key  # canonical key, not the raw input
    return payload


@router.get("/validate")
async def validate_address(governorate: str = Query(...), city: str = Query(None)):
    key = normalize_governorate(governorate)
    if not key:
        return {"valid": False, "governorate": governorate, "canonical": None}
    return {
        "valid": validate_egyptian_address(key, city),
        "governorate": governorate,
        "canonical": key,
    }
