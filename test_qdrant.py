from dotenv import load_dotenv
load_dotenv(override=True)
from src.memory_engine import MemoryEngine
import os

engine = MemoryEngine()
stats = engine.get_stats()
url = os.getenv('QDRANT_URL', '')

print()
print("=== QDRANT STATUS ===")
print("Points stored :", stats['points_count'])
print("Status        :", stats['status'])
if url:
    print("Backend       : CLOUD (AWS)")
    print("URL           :", url[:60] + "...")
else:
    print("Backend       : LOCAL (on-disk)")
print("=== TEST PASSED ===")
