from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(
    title="Telegram Storage API",
    description="API for managing files stored on Telegram",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/files")
async def list_files():
    """Temporary endpoint while developing"""
    return {
        "files": [
            {
                "id": "sample-id-1",
                "name": "example-document.pdf",
                "size": 1024 * 1024 * 2,  # 2MB
                "mime_type": "application/pdf",
                "category": "document",
                "created_at": "2025-04-17T12:00:00Z"
            },
            {
                "id": "sample-id-2",
                "name": "vacation-photo.jpg",
                "size": 1024 * 1024,  # 1MB
                "mime_type": "image/jpeg",
                "category": "image",
                "created_at": "2025-04-16T14:30:00Z"
            }
        ]
    }

@app.get("/api/categories")
async def get_categories():
    """Return sample categories"""
    return {
        "categories": ["document", "image", "video", "audio", "archive", "other"]
    }

@app.get("/api/user/profile")
async def get_user_profile():
    """Return sample user profile"""
    return {
        "id": "user-1",
        "email": "demo@example.com",
        "is_active": True,
        "telegram_id": 12345678
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
