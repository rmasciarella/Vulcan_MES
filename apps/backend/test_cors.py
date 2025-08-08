#!/usr/bin/env python3
"""Simple FastAPI server to test CORS configuration with Netlify frontend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os

# Create FastAPI app
app = FastAPI(title="CORS Test Server")

# Get frontend URL from environment or use default
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://vulcanmes.netlify.app")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "CORS Test Server Running", "frontend_url": FRONTEND_URL}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "cors_configured": True}

@app.get("/api/test")
async def test_endpoint():
    return {
        "message": "Test endpoint working",
        "allowed_origins": [FRONTEND_URL, "http://localhost:3000"],
        "credentials": "allowed"
    }

if __name__ == "__main__":
    print(f"Starting CORS test server with frontend URL: {FRONTEND_URL}")
    print("Server will be available at http://localhost:8000")
    print("API endpoints: /api/health, /api/test")
    uvicorn.run(app, host="0.0.0.0", port=8000)