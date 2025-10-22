import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference
from tortoise import Tortoise

from cat.db.database import init_db
from cat.env import get_env
from cat.routes import (
    home,
    auth,
    settings,
    chats,
    contexts,
    status
)
from cat.routes.plugins import plugins
from cat.routes.websocket import websocket
from cat.routes.static import static
from cat.routes.openapi import get_openapi_configuration_function
from cat.looking_glass.cheshire_cat import CheshireCat
from cat.utils import get_base_path


@asynccontextmanager
async def lifespan(app: FastAPI):

    # init DB
    await init_db()

    #  ^._.^ 
    ccat = CheshireCat()
    await ccat.bootstrap(app)

    yield
    
    # cleanup
    await Tortoise.close_connections()


# REST API
cheshire_cat_api = FastAPI(
    lifespan=lifespan,
    #openapi_url=None,
    docs_url=None,
    redoc_url=None,
    title="Cheshire Cat AI",
    license_info={
        "name": "GPL-3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
    },
)

# Configures the CORS middleware for the FastAPI app
cors_enabled = get_env("CCAT_CORS_ENABLED")
if cors_enabled == "true":
    cors_allowed_origins_str = get_env("CCAT_CORS_ALLOWED_ORIGINS")
    origins = cors_allowed_origins_str.split(",") if cors_allowed_origins_str else ["*"]
    cheshire_cat_api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Add routers
for r in [
    home, status, auth, chats, contexts, settings,
    plugins, static, websocket
]:
    cheshire_cat_api.include_router(r.router)


# Endpoint playground
@cheshire_cat_api.get("/docs", include_in_schema=False)
async def scalar_docs():
    cheshire_cat_api.openapi = get_openapi_configuration_function(cheshire_cat_api)
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title=cheshire_cat_api.title,
        scalar_favicon_url="https://cheshirecat.ai/wp-content/uploads/2023/10/Logo-Cheshire-Cat.svg",
    )

# UI assets
ui_static_dir = os.path.join(get_base_path(), "routes/static/core_static_folder/ui")
cheshire_cat_api.mount("/ui", StaticFiles(directory=ui_static_dir), name="ui")