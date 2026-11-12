import fastapi

import presentation.deps

router = fastapi.APIRouter()


@router.get("/health", dependencies=[fastapi.Depends(presentation.deps.check_database)])
def health() -> dict[str, str]:
    return {"status": "ok"}
