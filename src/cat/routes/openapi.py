
from importlib.metadata import metadata
from fastapi import FastAPI, APIRouter, Request
from fastapi.openapi.utils import get_openapi
from scalar_fastapi import get_scalar_api_reference

router = APIRouter()

# Endpoint playground
@router.get("/docs", include_in_schema=False)
async def scalar_docs(r: Request):
    r.app.openapi = get_openapi_configuration_function(r.app)
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title=r.app.title,
        scalar_favicon_url="https://cheshirecat.ai/wp-content/uploads/2023/10/Logo-Cheshire-Cat.svg",
    )

def get_openapi_configuration_function(cheshire_cat_api: FastAPI):
    # Configure openAPI schema for swagger and redoc
    def custom_openapi():
        if cheshire_cat_api.openapi_schema:
            return cheshire_cat_api.openapi_schema

        meta = metadata("cheshire-cat-ai")

        openapi_schema = get_openapi(
            title=f"🐱 Cheshire Cat AI - {meta.get('version')}",
            version=meta.get("version", "unknown"),
            description=meta.get("Summary"),
            routes=cheshire_cat_api.routes,
            external_docs={
                "description": "Cheshire Cat AI Documentation",
                "url": "https://cheshire-cat-ai.github.io/docs/",
            }
        )

        cheshire_cat_api.openapi_schema = openapi_schema
        return cheshire_cat_api.openapi_schema

    return custom_openapi
