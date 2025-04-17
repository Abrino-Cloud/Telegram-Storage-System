# Telegram Storage System

A self-hosted solution to use Telegram as your personal file storage system with a web UI.

## Overview

This system uses Telegram as a backend storage solution (similar to S3) while providing a user-friendly web interface to browse, upload, and manage your files. All files are stored entirely on Telegram's servers, with only metadata kept in a local database for fast searching and categorization.

## Features

- 🤖 Telegram bot (AbrinoStorage_bot) as your storage backend
- 🔐 Secure authentication with email/password + 2FA
- 🔄 Magic link authentication via Telegram
- 📂 File categorization (Music, Videos, Documents, etc.)
- 🔍 Fast search through metadata
- ↔️ Bi-directional access (upload/download via bot or web UI)
- 🐳 Fully dockerized deployment

## Prerequisites

- Telegram Bot Token (from BotFather)
- Docker and Docker Compose installed on your server
- Domain name (optional but recommended for secure access)

## Setup Instructions

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command and follow the instructions
3. Name your bot (e.g., "AbrinoStorage")
4. Create a username for your bot (e.g., "AbrinoStorage_bot")
5. Save the API token provided by BotFather

### 2. Configure Environment Variables

Create a `.env` file in the project root with the following variables:

```
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_USER_ID=your_telegram_user_id

# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=telegram_storage
POSTGRES_HOST=postgres

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Application Configuration
SECRET_KEY=your_secure_secret_key_for_jwt
ADMIN_EMAIL=your_email@example.com
ADMIN_PASSWORD=your_secure_admin_password
ENABLE_REGISTRATION=true  # Set to false after creating your account
```

### 3. Deploy with Docker Compose

```bash
# Clone the repository
git clone https://github.com/yourusername/telegram-storage.git
cd telegram-storage

# Start the services
docker compose up -d

# Check logs
docker compose logs -f
```

The application will be available at `http://your-server-ip:8080`

### 4. First-time Setup

1. Access the web UI and register using the admin email from your `.env` file
2. Set up 2FA for additional security (optional but recommended)
3. Start uploading files either through the web UI or by sending them to your bot

## Usage

### Web UI

- Browse files by categories
- Upload new files
- Search through your files
- Download files directly

### Telegram Bot

- Send any file to your bot to store it
- Use commands like:
  - `/categories` - List all categories
  - `/search <term>` - Search for files
  - `/recent` - Show recently uploaded files

## Architecture

- **Frontend**: Vue.js application
- **Backend**: Python FastAPI
- **Database**: PostgreSQL for metadata storage
- **Cache**: Redis for performance optimization
- **Storage**: Telegram Bot API

## Security Considerations

- All files are stored on Telegram's servers with their encryption
- Only metadata is stored in your local database
- Authentication with email/password + optional 2FA
- Magic link authentication available through Telegram

## Limitations

- Maximum file size: 2GB (Telegram's limit)
- Rate limits apply based on Telegram's API restrictions
- Not recommended for highly sensitive data

## Maintenance

### Backup

The only critical data to backup is your PostgreSQL database, which contains file metadata and user information:

```bash
docker compose exec postgres pg_dump -U postgres telegram_storage > backup.sql
```

### Updates

```bash
git pull
docker compose down
docker compose up -d --build
```

## Troubleshooting

### Rate Limit Issues

If you're experiencing rate limit issues with Telegram:

1. Check Redis logs for rate limit warnings
2. Consider increasing cache TTLs in the settings
3. Implement a more aggressive batching strategy for uploads

### Connection Problems

If the bot is not responding:

1. Verify your Telegram token is correct
2. Check if the bot is running with `docker compose ps`
3. Inspect logs with `docker compose logs telegram-bot`

## Contributing

This is a personal project, but contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT