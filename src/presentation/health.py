import collections.abc

import fastapi


def router(check_database: collections.abc.Callable[[], None]) -> fastapi.APIRouter:
    routes = fastapi.APIRouter()

    @routes.get("/health")
    def health() -> dict[str, str]:
        try:
            check_database()
        except ConnectionError as error:
            raise fastapi.HTTPException(503, "Database unavailable") from error
        return {"status": "ok"}

    return routes
