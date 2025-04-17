import logging
from sqlalchemy.ext.asyncio import AsyncSession

# Create a logger instance
logger = logging.getLogger(__name__)

async def init_db(db: AsyncSession) -> None:
    """
    Initialize database with required tables
    """
    try:
        # Execute schema file
        with open("app/db/schema.sql", "r") as f:
            schema_sql = f.read()
        
        # Split the schema into separate statements
        statements = schema_sql.split(';')
        
        for statement in statements:
            if statement.strip():
                await db.execute(statement)
        
        await db.commit()
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
