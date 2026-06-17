from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import os
import time

load_dotenv()

from .limiter import limiter
from .routes import router

docs_enabled = os.environ.get("API_DOCS_ENABLED", "").lower() in ("1", "true", "yes")

app = FastAPI(title="Pi Analysis API", docs_url="/docs" if docs_enabled else None, redoc_url="/redoc" if docs_enabled else None, openapi_url="/openapi.json" if docs_enabled else None)


async def scanner_block_middleware(request, call_next):
    path = request.url.path.lower()
    agent = request.headers.get("user-agent", "").lower()
    if any(p in path for p in ("/admin", "/wp-", "/wordpress", "/phpmyadmin", "/mysql", "/backup", "/config", "/.env", "/.git", "/vendor", "/shell", "/cgi-")):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    if any(bot in agent for bot in ("masscan", "zgrab", "nmap", "nikto", "sqlmap", "acunetix", "nessus", "openvas")):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    response = await call_next(request)
    return response


app.add_middleware(BaseHTTPMiddleware, dispatch=scanner_block_middleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workspace_dir = Path(os.environ.get("WORKSPACE_DIR", "./workspaces"))
workspace_dir.mkdir(parents=True, exist_ok=True)

app.include_router(router)

app.mount("/files", StaticFiles(directory=str(workspace_dir)), name="files")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)