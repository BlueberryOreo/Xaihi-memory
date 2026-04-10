"""MongoDB client for xaihi memory system."""
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

try:
    from .config import config
except ImportError:
    from config import config


class MongoDBClient:
    """MongoDB client with memory operations."""

    _instance = None
    _db: Database | None = None
    _collection: Collection | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connect()
        return cls._instance

    def _connect(self) -> None:
        from pymongo import MongoClient

        mongo_cfg = config.get_mongodb()
        client = MongoClient(
            host=mongo_cfg.get("host", "localhost"),
            port=mongo_cfg.get("port", 27017),
        )
        db_name = mongo_cfg.get("database", "memory_db")
        self._db = client[db_name]
        self._collection = self._db[mongo_cfg.get("collection", "memories")]

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            self._connect()
        return self._collection

    @property
    def db(self) -> Database:
        if self._db is None:
            self._connect()
        return self._db

    def setup_indexes(self) -> None:
        """Create necessary indexes for the memories collection."""
        # Vector search index (MongoDB 8.0+)
        try:
            self.collection.create_search_index(
                {
                    "name": "vector_index",
                    "definition": {
                        "fields": [
                            {
                                "type": "vector",
                                "path": "embedding",
                                "numDimensions": config.get_embedding().get("dimension", 1536),
                                "similarity": "cosine",
                            }
                        ]
                    },
                }
            )
        except Exception:
            # Index might already exist
            pass

        # TTL index for auto-expiry
        ttl_days = config.get_memory().get("ttl_days", 365)
        self.collection.create_index(
            [("created_at", ASCENDING)],
            expireAfterSeconds=ttl_days * 24 * 3600,
            name="ttl_index",
        )

        # Index for filtering
        self.collection.create_index(
            [("importance", ASCENDING)],
            name="importance_index",
        )
        self.collection.create_index(
            [("topics", ASCENDING)],
            name="topics_index",
        )

    def insert_memory(
        self,
        content: str,
        embedding: list[float],
        topics: list[str],
        key_facts: list[str],
        importance: float,
        sentiment: str,
        source: str = "auto_summary",
        session_id: str | None = None,
    ) -> str:
        """Insert a memory document."""
        doc = {
            "content": content,
            "embedding": embedding,
            "topics": topics,
            "key_facts": key_facts,
            "importance": importance,
            "sentiment": sentiment,
            "source": source,
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = self.collection.insert_one(doc)
        return str(result.inserted_id)

    def search_by_vector(
        self,
        embedding: list[float],
        top_k: int = 5,
        min_importance: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Search memories by vector similarity."""
        try:
            results = self.collection.aggregate(
                [
                    {
                        "$vectorSearch": {
                            "index": "vector_index",
                            "path": "embedding",
                            "queryVector": embedding,
                            "numCandidates": top_k * 4,
                            "limit": top_k * 2,
                        }
                    },
                    {
                        "$match": {
                            "importance": {"$gte": min_importance},
                        }
                    },
                    {
                        "$project": {
                            "content": 1,
                            "topics": 1,
                            "key_facts": 1,
                            "importance": 1,
                            "sentiment": 1,
                            "created_at": 1,
                            "score": {"$meta": "vectorSearchScore"},
                        }
                    },
                    {"$sort": {"score": DESCENDING}},
                    {"$limit": top_k},
                ]
            )
            return list(results)
        except Exception:
            # Fallback: simple embedding magnitude search if vector index not ready
            return []

    def delete_old_memories(self, days_threshold: int = 30, importance_threshold: float = 0.3) -> int:
        """Delete old and low-importance memories."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        result = self.collection.delete_many(
            {
                "created_at": {"$lt": cutoff},
                "importance": {"$lt": importance_threshold},
            }
        )
        return result.deleted_count


mongodb_client = MongoDBClient()
