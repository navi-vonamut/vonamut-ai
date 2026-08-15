import asyncio
import logging
from src.sports.rag.qdrant_sports_manager import get_qdrant_sports_manager

logging.basicConfig(level=logging.INFO)

async def test_qdrant():
    print("Testing QdrantSportsManager...")
    mgr = get_qdrant_sports_manager()
    print("Initializing collection...")
    init_res = mgr.init_collection()
    print(f"Collection initialized: {init_res}")
    
    print("Adding insider post...")
    res = mgr.add_insider_post({
        "text": "СРОЧНО: У Динамо Москва травмировался основной вратарь.",
        "source": "@nobel_insider",
        "team1": "Спартак Москва",
        "team2": "Динамо Москва"
    })
    print(f"Post added: {res}")

if __name__ == "__main__":
    asyncio.run(test_qdrant())
