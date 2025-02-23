from motor.motor_asyncio import AsyncIOMotorClient

from app.core.settings import settings

client = AsyncIOMotorClient(settings.mongo_uri)
db = client[settings.db_name]
