from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import uuid
import os

class MemoryEngine:
    def __init__(self):
        # PRIORITY: Use In-Memory for Hackathon stability
        # If you really want cloud, uncomment the next lines, but :memory: is safer.
        self.client = QdrantClient(":memory:") 
        self.collection = "civic_defense_grid"
        
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=768, distance=Distance.COSINE),
        )

    def search_duplicate(self, vector):
        try:
            # Standard Search for v1.0+
            hits = self.client.search(
                collection_name=self.collection,
                query_vector=vector,
                limit=1,
                score_threshold=0.98
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
        return self.client.get_collection(self.collection)