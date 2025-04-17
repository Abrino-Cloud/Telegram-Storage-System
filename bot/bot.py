import logging
import asyncio
import httpx
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import redis.asyncio as redis
import os
from datetime import datetime
from dotenv import load_dotenv
import re
import json

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ADMIN_USER_ID = int(os.getenv("TELEGRAM_ADMIN_USER_ID", "0"))
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# Database setup
DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}"
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Redis setup
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# File categorization patterns
FILE_CATEGORIES = {
    "image": ["image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"],
    "video": ["video/mp4", "video/mpeg", "video/quicktime", "video/webm"],
    "audio": ["audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav", "audio/webm"],
    "document": ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    "spreadsheet": ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    "presentation": ["application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"],
    "archive": ["application/zip", "application/x-rar-compressed", "application/x-tar", "application/gzip"],
    "code": ["text/plain", "application/json", "text/html", "text/css", "application/javascript"],
}

# File extension patterns
FILE_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"],
    "video": [".mp4", ".mpeg", ".mov", ".webm", ".avi", ".mkv"],
    "audio": [".mp3", ".m4a", ".ogg", ".wav", ".flac"],
    "document": [".pdf", ".doc", ".docx", ".txt", ".rtf"],
    "spreadsheet": [".xls", ".xlsx", ".csv"],
    "presentation": [".ppt", ".pptx"],
    "archive": [".zip", ".rar", ".tar", ".gz", ".7z"],
    "code": [".py", ".js", ".html", ".css", ".json", ".xml", ".java", ".c", ".cpp"],
}

# Utility functions
async def get_db():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session

async def get_redis():
    """Get Redis connection"""
    return redis.Redis(connection_pool=redis_pool)

def categorize_file(file_name, mime_type):
    """Categorize file based on mime type and extension"""
    # Check by mime type first
    for category, mime_types in FILE_CATEGORIES.items():
        if mime_type in mime_types:
            return category
    
    # Check by extension if mime type not found
    file_extension = os.path.splitext(file_name.lower())[1]
    for category, extensions in FILE_EXTENSIONS.items():
        if file_extension in extensions:
            return category
    
    # Default category
    return "other"

async def save_file_metadata(telegram_file_id, file_name, file_size, mime_type, user_id):
    """Save file metadata to database"""
    category = categorize_file(file_name, mime_type)
    
    async with AsyncSessionLocal() as session:
        # Create SQL query to insert file metadata
        query = """
        INSERT INTO files (name, telegram_file_id, size, mime_type, category, user_id, created_at, updated_at)
        VALUES (:name, :telegram_file_id, :size, :mime_type, :category, :user_id, :created_at, :updated_at)
        RETURNING id
        """
        
        now = datetime.utcnow()
        result = await session.execute(query, {
            "name": file_name,
            "telegram_file_id": telegram_file_id,
            "size": file_size,
            "mime_type": mime_type,
            "category": category,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now
        })
        
        file_id = result.scalar_one()
        await session.commit()
        
        # Invalidate Redis cache
        r = await get_redis()
        await r.delete(f"files:{user_id}:*")
        
        return file_id

async def get_user_by_telegram_id(telegram_id):
    """Get user by Telegram ID"""
    async with AsyncSessionLocal() as session:
        query = """
        SELECT id, email, is_active, twofa_enabled, telegram_id
        FROM users
        WHERE telegram_id = :telegram_id
        """
        
        result = await session.execute(query, {"telegram_id": telegram_id})
        user = result.fetchone()
        
        return user

async def register_telegram_user(telegram_id, username=None):
    """Register new user with Telegram ID"""
    async with AsyncSessionLocal() as session:
        # Check if admin has already been registered
        if telegram_id == TELEGRAM_ADMIN_USER_ID:
            query = """
            SELECT id FROM users WHERE email = :email
            """
            result = await session.execute(query, {"email": os.getenv("ADMIN_EMAIL")})
            admin = result.fetchone()
            
            if admin:
                # Update admin's Telegram ID
                update_query = """
                UPDATE users SET telegram_id = :telegram_id WHERE id = :id
                """
                await session.execute(update_query, {"telegram_id": telegram_id, "id": admin[0]})
                await session.commit()
                return admin[0]
        
        # Generate email based on Telegram ID
        email = f"telegram_{telegram_id}@telegram.user"
        
        # Create new user
        query = """
        INSERT INTO users (email, hashed_password, is_active, telegram_id, created_at, updated_at)
        VALUES (:email, :hashed_password, :is_active, :telegram_id, :created_at, :updated_at)
        RETURNING id
        """
        
        now = datetime.utcnow()
        result = await session.execute(query, {
            "email": email,
            "hashed_password": "telegram_only_user",  # These users can only login via Telegram
            "is_active": True,
            "telegram_id": telegram_id,
            "created_at": now,
            "updated_at": now
        })
        
        user_id = result.scalar_one()
        await session.commit()
        
        return user_id

async def get_user_files(user_id, category=None, limit=10):
    """Get user files with optional category filter"""
    async with AsyncSessionLocal() as session:
        query = """
        SELECT id, name, telegram_file_id, size, mime_type, category, created_at
        FROM files
        WHERE user_id = :user_id
        """
        
        params = {"user_id": user_id}
        
        if category and category != "all":
            query += " AND category = :category"
            params["category"] = category
        
        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await session.execute(query, params)
        files = result.fetchall()
        
        return files

async def search_files(user_id, search_term):
    """Search user files by name"""
    async with AsyncSessionLocal() as session:
        query = """
        SELECT id, name, telegram_file_id, size, mime_type, category, created_at
        FROM files
        WHERE user_id = :user_id AND name ILIKE :search_term
        ORDER BY created_at DESC LIMIT 20
        """
        
        result = await session.execute(query, {
            "user_id": user_id,
            "search_term": f"%{search_term}%"
        })
        
        files = result.fetchall()
        return files

async def get_user_categories(user_id):
    """Get all categories used by a user"""
    async with AsyncSessionLocal() as session:
        query = """
        SELECT DISTINCT category FROM files
        WHERE user_id = :user_id
        ORDER BY category
        """
        
        result = await session.execute(query, {"user_id": user_id})
        categories = [row[0] for row in result.fetchall()]
        
        return categories

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Check if user exists
    existing_user = await get_user_by_telegram_id(user.id)
    
    if not existing_user:
        user_id = await register_telegram_user(user.id, user.username)
        await update.message.reply_text(
            f"Welcome to AbrinoStorage Bot! 📦\n\n"
            f"I'll help you store and organize your files. "
            f"Simply send me any file and I'll save it for you.\n\n"
            f"You can access your files through the web interface or directly from this chat. "
            f"Type /help to see all available commands."
        )
    else:
        await update.message.reply_text(
            f"Welcome back! 👋\n\n"
            f"Ready to manage your files. Send me any file to store it, "
            f"or use /files to browse your collection."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "🤖 *AbrinoStorage Bot Commands* 🤖\n\n"
        "/files - List your recent files\n"
        "/files <category> - List files in a specific category\n"
        "/categories - See all your file categories\n"
        "/search <term> - Search for files by name\n"
        "/recent - Show your 10 most recent files\n\n"
        "Simply send any file to store it in your personal collection.\n\n"
        "Access all your files through the web interface for a better experience!"
    )
    
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /files command"""
    user = update.effective_user
    existing_user = await get_user_by_telegram_id(user.id)
    
    if not existing_user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    # Check if category provided
    category = None
    if context.args:
        category = context.args[0].lower()
    
    # Get files
    files = await get_user_files(existing_user[0], category)
    
    if not files:
        if category:
            await update.message.reply_text(f"You don't have any files in the '{category}' category.")
        else:
            await update.message.reply_text("You don't have any files yet. Send me some files to get started!")
        return
    
    # Format response
    response = "📁 *Your Files*:\n\n"
    for i, file in enumerate(files, 1):
        file_id, name, telegram_file_id, size, mime_type, file_category, created_at = file
        size_in_mb = size / (1024 * 1024)
        
        response += f"{i}. *{name}*\n"
        response += f"   - Category: {file_category}\n"
        response += f"   - Size: {size_in_mb:.2f} MB\n"
        response += f"   - Uploaded: {created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def categories_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /categories command"""
    user = update.effective_user
    existing_user = await get_user_by_telegram_id(user.id)
    
    if not existing_user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    # Get categories
    categories = await get_user_categories(existing_user[0])
    
    if not categories:
        await update.message.reply_text("You don't have any files yet. Send me some files to get started!")
        return
    
    # Format response
    response = "📂 *Your File Categories*:\n\n"
    for i, category in enumerate(categories, 1):
        response += f"{i}. *{category}*\n"
    
    response += "\nUse /files <category> to see files in a specific category."
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command"""
    user = update.effective_user
    existing_user = await get_user_by_telegram_id(user.id)
    
    if not existing_user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    # Check if search term provided
    if not context.args:
        await update.message.reply_text("Please provide a search term. Example: /search document")
        return
    
    search_term = " ".join(context.args)
    
    # Search files
    files = await search_files(existing_user[0], search_term)
    
    if not files:
        await update.message.reply_text(f"No files found matching '{search_term}'.")
        return
    
    # Format response
    response = f"🔍 *Search Results for '{search_term}'*:\n\n"
    for i, file in enumerate(files, 1):
        file_id, name, telegram_file_id, size, mime_type, category, created_at = file
        size_in_mb = size / (1024 * 1024)
        
        response += f"{i}. *{name}*\n"
        response += f"   - Category: {category}\n"
        response += f"   - Size: {size_in_mb:.2f} MB\n"
        response += f"   - Uploaded: {created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recent command"""
    user = update.effective_user
    existing_user = await get_user_by_telegram_id(user.id)
    
    if not existing_user:
        await update.message.reply_text("Please use /start to register first.")
        return
    
    # Get recent files
    files = await get_user_files(existing_user[0], limit=10)
    
    if not files:
        await update.message.reply_text("You don't have any files yet. Send me some files to get started!")
        return
    
    # Format response
    response = "🕒 *Your Recent Files*:\n\n"
    for i, file in enumerate(files, 1):
        file_id, name, telegram_file_id, size, mime_type, category, created_at = file
        size_in_mb = size / (1024 * 1024)
        
        response += f"{i}. *{name}*\n"
        response += f"   - Category: {category}\n"
        response += f"   - Size: {size_in_mb:.2f} MB\n"
        response += f"   - Uploaded: {created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    await update.message.reply_text(response, parse_mode="Markdown")

# File handlers
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages"""
    user = update.effective_user
    document = update.message.document
    
    # Check if user exists
    existing_user = await get_user_by_telegram_id(user.id)
    if not existing_user:
        user_id = await register_telegram_user(user.id, user.username)
    else:
        user_id = existing_user[0]
    
    # Save file metadata
    file_id = await save_file_metadata(
        telegram_file_id=document.file_id,
        file_name=document.file_name,
        file_size=document.file_size,
        mime_type=document.mime_type,
        user_id=user_id
    )
    
    # Get category
    category = categorize_file(document.file_name, document.mime_type)
    
    await update.message.reply_text(
        f"✅ File saved successfully!\n\n"
        f"📄 Name: {document.file_name}\n"
        f"📁 Category: {category}\n"
        f"📊 Size: {document.file_size / (1024 * 1024):.2f} MB\n\n"
        f"You can access this file through the web interface or by using /files command."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages"""
    user = update.effective_user
    photo = update.message.photo[-1]  # Get the largest photo
    
    # Check if user exists
    existing_user = await get_user_by_telegram_id(user.id)
    if not existing_user:
        user_id = await register_telegram_user(user.id, user.username)
    else:
        user_id = existing_user[0]
    
    # Generate file name
    file_name = f"photo_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    
    # Save file metadata
    file_id = await save_file_metadata(
        telegram_file_id=photo.file_id,
        file_name=file_name,
        file_size=photo.file_size,
        mime_type="image/jpeg",
        user_id=user_id
    )
    
    await update.message.reply_text(
        f"✅ Photo saved successfully!\n\n"
        f"📄 Name: {file_name}\n"
        f"📁 Category: image\n"
        f"📊 Size: {photo.file_size / (1024 * 1024):.2f} MB\n\n"
        f"You can access this photo through the web interface or by using /files command."
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle audio messages"""
    user = update.effective_user
    audio = update.message.audio
    
    # Check if user exists
    existing_user = await get_user_by_telegram_id(user.id)
    if not existing_user:
        user_id = await register_telegram_user(user.id, user.username)
    else:
        user_id = existing_user[0]
    
    # Generate file name if not provided
    file_name = audio.file_name
    if not file_name:
        file_name = f"audio_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp3"
    
    # Save file metadata
    file_id = await save_file_metadata(
        telegram_file_id=audio.file_id,
        file_name=file_name,
        file_size=audio.file_size,
        mime_type=audio.mime_type or "audio/mpeg",
        user_id=user_id
    )
    
    await update.message.reply_text(
        f"✅ Audio saved successfully!\n\n"
        f"📄 Name: {file_name}\n"
        f"📁 Category: audio\n"
        f"📊 Size: {audio.file_size / (1024 * 1024):.2f} MB\n\n"
        f"You can access this audio through the web interface or by using /files command."
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video messages"""
    user = update.effective_user
    video = update.message.video
    
    # Check if user exists
    existing_user = await get_user_by_telegram_id(user.id)
    if not existing_user:
        user_id = await register_telegram_user(user.id, user.username)
    else:
        user_id = existing_user[0]
    
    # Generate file name if not provided
    file_name = video.file_name
    if not file_name:
        file_name = f"video_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
    
    # Save file metadata
    file_id = await save_file_metadata(
        telegram_file_id=video.file_id,
        file_name=file_name,
        file_size=video.file_size,
        mime_type=video.mime_type or "video/mp4",
        user_id=user_id
    )
    
    await update.message.reply_text(
        f"✅ Video saved successfully!\n\n"
        f"📄 Name: {file_name}\n"
        f"📁 Category: video\n"
        f"📊 Size: {video.file_size / (1024 * 1024):.2f} MB\n\n"
        f"You can access this video through the web interface or by using /files command."
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""
    user = update.effective_user
    voice = update.message.voice
    
    # Check if user exists
    existing_user = await get_user_by_telegram_id(user.id)
    if not existing_user:
        user_id = await register_telegram_user(user.id, user.username)
    else:
        user_id = existing_user[0]
    
    # Generate file name
    file_name = f"voice_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.ogg"
    
    # Save file metadata
    file_id = await save_file_metadata(
        telegram_file_id=voice.file_id,
        file_name=file_name,
        file_size=voice.file_size,
        mime_type="audio/ogg",
        user_id=user_id
    )
    
    await update.message.reply_text(
        f"✅ Voice message saved successfully!\n\n"
        f"📄 Name: {file_name}\n"
        f"📁 Category: audio\n"
        f"📊 Size: {voice.file_size / (1024 * 1024):.2f} MB\n\n"
        f"You can access this voice message through the web interface or by using /files command."
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Notify user
    if update.effective_message:
        await update.effective_message.reply_text(
            "Sorry, something went wrong. Please try again later."
        )

async def health_check():
    """Health check endpoint for Docker"""
    while True:
        try:
            # Check database connection
            async with AsyncSessionLocal() as session:
                await session.execute("SELECT 1")
            
            # Check Redis connection
            r = await get_redis()
            await r.ping()
            
            logger.info("Health check passed")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        
        await asyncio.sleep(30)

async def main():
    """Start the bot"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("files", files_command))
    application.add_handler(CommandHandler("categories", categories_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("recent", recent_command))
    
    # Register message handlers
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start health check in background
    asyncio.create_task(health_check())
    
    # Run the bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Keep the script running
    try:
        await asyncio.Future()  # Run forever
    except (KeyboardInterrupt, SystemExit):
        await application.stop()
        await application.updater.stop()

if __name__ == "__main__":
    asyncio.run(main())
