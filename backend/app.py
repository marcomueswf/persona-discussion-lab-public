"""FastAPI application composition root.

This module wires routers, middleware, and static UI hosting. API routes are
mounted under /api while the OpenUI5 webapp is served from the root path.
"""


from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv
from backend.runtime_paths import get_bundle_root, get_runtime_file
from backend.configurations_api import router as configurations_router
from backend.environment_api import router as environment_router
from backend.discussions_api import router as discussions_router
from backend.personas_api import router as personas_router
from backend.results_api import router as results_router

app = FastAPI(title="Persona Discussion Lab API")

# Allow the UI5 dev server (or other local dev origins) to call the API.
# In production you should restrict allowed origins appropriately.
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend `webapp` directory at the application root so
# visiting `/` should return the UI. Keep API routes under `/api/*`.
project_root = get_bundle_root()
webapp_dir = project_root / "webapp"
load_dotenv(get_runtime_file(".env"))


@app.get("/api/health")
def health():
    return {"status": "ok"}

app.include_router(personas_router, prefix="/api")
app.include_router(discussions_router, prefix="/api")
app.include_router(configurations_router, prefix="/api")
app.include_router(environment_router, prefix="/api")
app.include_router(results_router, prefix="/api")


# Mount static UI after API routes so API endpoints like /api/personas are matched first.
if webapp_dir.exists():
    app.mount("/", StaticFiles(directory=str(webapp_dir), html=True), name="webapp")


@app.get("/favicon.ico")
def favicon():
    # Try to serve a favicon from the webapp folder if present
    ico = webapp_dir / "favicon.ico"
    if ico.exists():
        return FileResponse(str(ico))
    return JSONResponse(status_code=204, content={})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
