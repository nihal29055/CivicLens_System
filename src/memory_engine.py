from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import uuid
import os
from urllib.parse import urlparse

class MemoryEngine:
    def __init__(self):
        self.collection = "civic_defense_grid"
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_key = os.getenv("QDRANT_API_KEY")
        
        self.client = None
        if qdrant_url and urlparse(qdrant_url).scheme in {"http", "https"}:
            try:
                print(f">> MEMORY ENGINE: Connecting to Cloud Qdrant at {qdrant_url}")
                self.client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
                self.client.get_collections()
            except Exception as e:
                print(f">> WARNING: Cloud Qdrant unavailable ({e}). Falling back to local storage.")

        if self.client is None:
            if qdrant_url:
                print(">> WARNING: QDRANT_URL must include http:// or https://. Using local storage.")
            # Use persistent local storage
            db_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "qdrant_db"))
            try:
                print(f">> MEMORY ENGINE: Initializing local persistent Qdrant at {db_path}")
                self.client = QdrantClient(path=db_path)
            except Exception as e:
                print(f">> WARNING: Local persistent Qdrant failed ({e}). Falling back to in-memory.")
                self.client = QdrantClient(":memory:")
        
        # Check if collection exists before creating it
        exists = False
        try:
            # Try collection_exists (v1.8+)
            exists = self.client.collection_exists(self.collection)
        except AttributeError:
            try:
                self.client.get_collection(self.collection)
                exists = True
            except Exception:
                exists = False
        
        if not exists:
            print(f">> MEMORY ENGINE: Creating collection '{self.collection}'")
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
        else:
            print(f">> MEMORY ENGINE: Loaded existing collection '{self.collection}'")

    def search_duplicate(self, vector):
        try:
            # Standard Search for v1.0+
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=vector,
                limit=1,
                score_threshold=0.90 # Adjust threshold for visual description similarity
            )
            
            if hits:
                return True, hits[0].score, hits[0].payload
            return False, 0.0, None
            
        except AttributeError:
            # Fallback for older/different clients
            print(">> WARNING: using legacy search method")
            return False, 0.0, None
        except Exception as e:
            print(f"!! QDRANT ERROR: {e}")
            return False, 0.0, None

    def save_record(self, vector, metadata):
        try:
            self.client.upsert(
                collection_name=self.collection,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload=metadata
                    )
                ]
            )
        except Exception as e:
            print(f"!! SAVE ERROR: {e}")

    def get_stats(self):
        try:
            collection_info = self.client.get_collection(self.collection)
            return {
                "points_count": getattr(collection_info, "points_count", 0),
                "vectors_count": getattr(collection_info, "vectors_count", 0),
                "status": getattr(collection_info, "status", "unknown")
            }
        except Exception as e:
            print(f"!! STATS ERROR: {e}")
            return {"points_count": 0, "status": "error"}

    def reset_collection(self):
        """Deletes and recreates the Qdrant collection (wipes all vectors)."""
        try:
            self.client.delete_collection(self.collection)
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            print(">> MEMORY ENGINE: Collection reset successfully.")
            return True
        except Exception as e:
            print(f"!! RESET ERROR: {e}")
            return False
