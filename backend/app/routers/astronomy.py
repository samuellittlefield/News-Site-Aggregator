from fastapi import APIRouter

router = APIRouter(prefix="/api/astronomy", tags=["astronomy"])


@router.get("")
def get_sky():
    """Compute tonight's sky for SF Bay Area using ephem."""
    from app.services.astronomy import get_sky_tonight
    return get_sky_tonight()
