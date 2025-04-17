from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
import httpx
import asyncio
import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash
from app.api.deps import get_db, get_current_user, get_redis, get_telegram_client
from app.crud import files, users
from app.schemas.file import FileCreate, FileResponse, FileSearch
from app.schemas.user import UserCreate, UserLogin, UserResponse, MagicLinkRequest
from app.schemas.auth import Token
from app.utils.rate_limit import RateLimiter
from app.utils.file_categorizer import categorize_file

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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

# Rate limiter
rate_limiter = RateLimiter()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health check endpoints
    if request.url.path == "/health":
        return await call_next(request)
    
    client_ip = request.client.host
    redis = await get_redis()
    
    if not await rate_limiter.check_rate_limit(redis, client_ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please try again later."},
        )
    
    response = await call_next(request)
    return response

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# Auth endpoints
@app.post("/api/auth/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # Check if registration is enabled
    if not settings.ENABLE_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently disabled"
        )
    
    # Check if user already exists
    existing_user = await users.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = await users.create_user(db, user_data)
    return user

@app.post("/api/auth/login", response_model=Token)
async def login_user(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    # Get user by email
    user = await users.get_user_by_email(db, user_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check 2FA if enabled
    if user.twofa_enabled:
        if not user_data.twofa_code:
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={"require_2fa": True}
            )
        
        # Verify 2FA code
        if not await users.verify_2fa(db, user.id, user_data.twofa_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 2FA code"
            )
    
    # Generate token
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Store token in Redis for potential revocation
    await redis.setex(
        f"token:{access_token}",
        settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        str(user.id)
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/telegram-magic-link")
async def generate_magic_link(
    request_data: MagicLinkRequest,
    db: AsyncSession = Depends(get_db),
    telegram: httpx.AsyncClient = Depends(get_telegram_client),
    redis = Depends(get_redis)
):
    # Get user by email
    user = await users.get_user_by_email(db, request_data.email)
    if not user or not user.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or not linked to Telegram"
        )
    
    # Generate one-time token
    token = await users.generate_magic_link_token(db, user.id)
    magic_link = f"{settings.FRONTEND_URL}/auth/verify?token={token}"
    
    # Store token in Redis
    await redis.setex(
        f"magic_link:{token}",
        settings.MAGIC_LINK_EXPIRE_MINUTES * 60,
        str(user.id)
    )
    
    # Send via Telegram
    try:
        await telegram.post("sendMessage", json={
            "chat_id": user.telegram_id,
            "text": f"Your login link is valid for {settings.MAGIC_LINK_EXPIRE_MINUTES} minutes:\n\n{magic_link}"
        })
    except Exception as e:
        logger.error(f"Failed to send magic link via Telegram: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send magic link"
        )
    
    return {"message": "Magic link sent to your Telegram"}

@app.get("/api/auth/verify-magic-link", response_model=Token)
async def verify_magic_link(
    token: str,
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    # Check if token exists in Redis
    user_id = await redis.get(f"magic_link:{token}")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Delete token after use
    await redis.delete(f"magic_link:{token}")
    
    # Generate JWT token
    access_token = create_access_token(
        data={"sub": user_id.decode()},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Store token in Redis
    await redis.setex(
        f"token:{access_token}",
        settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id.decode()
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# File endpoints
@app.get("/api/files", response_model=List[FileResponse])
async def list_files(
    category: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    redis = Depends(get_redis)
):
    # Try to get from cache first
    cache_key = f"files:{current_user.id}:{category or 'all'}:{search or 'none'}:{skip}:{limit}"
    cached_files = await redis.get(cache_key)
    
    if cached_files:
        # Return cached files
        return FileResponse.parse_raw(cached_files)
    
    # Get files from database
    user_files = await files.get_files(
        db,
        user_id=current_user.id,
        category=category,
        search_term=search,
        skip=skip,
        limit=limit
    )
    
    # Cache results for 5 minutes
    await redis.setex(
        cache_key,
        300,  # 5 minutes
        FileResponse.json(user_files)
    )
    
    return user_files

@app.get("/api/files/{file_id}")
async def download_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    telegram: httpx.AsyncClient = Depends(get_telegram_client)
):
    # Get file from database
    file = await files.get_file_by_id(db, file_id)
    if not file or file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Get file info from Telegram
    try:
        response = await telegram.get(f"getFile?file_id={file.telegram_file_id}")
        file_data = response.json()
        
        if not file_data.get("ok"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on Telegram"
            )
        
        file_path = file_data["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
        
        # Stream file from Telegram
        async def stream_file():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", file_url) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
        
        # Update last accessed time
        await files.update_file_access(db, file_id)
        
        return StreamingResponse(
            stream_file(),
            media_type=file.mime_type,
            headers={"Content-Disposition": f"attachment; filename=\"{file.name}\""}
        )
    
    except Exception as e:
        logger.error(f"Failed to download file from Telegram: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file"
        )

@app.post("/api/files", response_model=FileResponse)
async def upload_file(
    file_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    telegram: httpx.AsyncClient = Depends(get_telegram_client)
):
    # Upload file to Telegram
    try:
        # Here you would handle the file upload to Telegram
        # For simplicity, we're assuming the file data includes the necessary information
        
        # Determine file category
        category = file_data.get("category") or categorize_file(
            file_data["name"],
            file_data["mime_type"]
        )
        
        # Create file in database
        new_file = FileCreate(
            name=file_data["name"],
            telegram_file_id=file_data["telegram_file_id"],
            size=file_data["size"],
            mime_type=file_data["mime_type"],
            category=category,
            user_id=current_user.id
        )
        
        file = await files.create_file(db, new_file)
        
        # Invalidate cache
        redis = await get_redis()
        await redis.delete(f"files:{current_user.id}:*")
        
        return file
    
    except Exception as e:
        logger.error(f"Failed to upload file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )

@app.delete("/api/files/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    telegram: httpx.AsyncClient = Depends(get_telegram_client),
    redis = Depends(get_redis)
):
    # Get file from database
    file = await files.get_file_by_id(db, file_id)
    if not file or file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete file from database
    await files.delete_file(db, file_id)
    
    # Invalidate cache
    await redis.delete(f"files:{current_user.id}:*")
    
    return {"message": "File deleted successfully"}

@app.get("/api/categories")
async def get_categories(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    redis = Depends(get_redis)
):
    # Try to get from cache first
    cache_key = f"categories:{current_user.id}"
    cached_categories = await redis.get(cache_key)
    
    if cached_categories:
        return {"categories": cached_categories.decode().split(",")}
    
    # Get categories from database
    user_categories = await files.get_user_categories(db, current_user.id)
    
    # Cache results for 15 minutes
    await redis.setex(
        cache_key,
        900,  # 15 minutes
        ",".join(user_categories)
    )
    
    return {"categories": user_categories}

@app.get("/api/user/profile", response_model=UserResponse)
async def get_user_profile(
    current_user = Depends(get_current_user)
):
    """Get current user profile"""
    return current_user

@app.post("/api/user/link-telegram")
async def link_telegram_account(
    telegram_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Link user account to Telegram"""
    await users.update_telegram_id(db, current_user.id, telegram_id)
    return {"message": "Telegram account linked successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)