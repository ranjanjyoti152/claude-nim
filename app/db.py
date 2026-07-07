from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_url)
    return _client


def get_db():
    return get_client()[settings.mongo_db]


# Collection accessors
def users():
    return get_db()["users"]


def api_keys():
    return get_db()["api_keys"]


def model_mappings():
    return get_db()["model_mappings"]


def usage():
    return get_db()["usage"]


async def init_indexes() -> None:
    await users().create_index("email", unique=True)
    await api_keys().create_index("prefix")
    await api_keys().create_index("owner_id")
    await model_mappings().create_index("slot", unique=True)
    await usage().create_index("created_at")
    await usage().create_index("owner_id")


async def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
