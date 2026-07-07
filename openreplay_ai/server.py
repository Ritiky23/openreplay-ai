import os
import difflib
import mimetypes

# Fix Windows registry mime type bugs
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from openreplay_ai.core.db import DBManager
from openreplay_ai.core.models import PromptDiffRequest

app = FastAPI(title="OpenReplay AI Studio Local Server")

# Allow CORS for development (when React runs on Vite port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
@app.get("/api/traces")
def get_traces():
    try:
        return DBManager.get_all_traces()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/traces/{trace_id}")
def get_trace(trace_id: str):
    try:
        trace_data = DBManager.get_trace_tree(trace_id)
        if not trace_data:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/prompt-diff")
def compare_prompts(req: PromptDiffRequest):
    """Computes a line-by-line diff between two prompts using python's difflib."""
    try:
        v1_lines = req.prompt_v1.splitlines(keepends=True)
        v2_lines = req.prompt_v2.splitlines(keepends=True)
        
        diff = list(difflib.ndiff(v1_lines, v2_lines))
        return {"diff": diff}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Resolve React pre-compiled directory
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "dashboard", "dist")

# If static assets exist, mount SPA routing fallback
@app.get("/{path_name:path}")
def serve_spa(path_name: str):
    # Avoid capturing API requests that got 404'd
    if path_name.startswith("api/"):
        raise HTTPException(status_code=404, detail="API Endpoint Not Found")
        
    # Check if the requested path corresponds to an actual file (e.g. assets, favicon)
    file_path = os.path.join(static_dir, path_name)
    if path_name and os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
        
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    # Fallback message if dashboard is not built
    return {
        "status": "online",
        "message": "OpenReplay AI Studio API is running, but UI has not been built yet.",
        "api_docs": "/docs"
    }
