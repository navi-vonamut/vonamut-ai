import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class RAGConfig(BaseModel):
    # Qdrant Vector DB Settings
    collection_name: str = "market_news_24h"
    embedding_model: str = "models/gemini-embedding-2"
    vector_size: int = 3072
    
    qdrant_url: str = Field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://qdrant:6333")
    )

    # API Keys
    google_api_key: str = Field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY", "")
    )
    tavily_api_key: str = Field(
        default_factory=lambda: os.getenv("TAVILY_API_KEY", "")
    )
    cryptopanic_api_key: str = Field(
        default_factory=lambda: os.getenv("CRYPTOPANIC_API_KEY", "")
    )

    # News Ingestion Settings
    max_search_results: int = 15
    news_ttl_hours: int = 48 # Retention period
    default_symbols: List[str] = Field(
        default_factory=lambda: ["BTC", "ETH", "SOL", "MACRO"]
    )

    def get_effective_qdrant_url(self) -> str:
        url = self.qdrant_url
        # If running outside docker on host, fallback from qdrant:6333 to localhost:6335
        if "http://qdrant:6333" in url and not os.path.exists("/.dockerenv"):
            url = url.replace("http://qdrant:6333", "http://localhost:6335")
        return url

rag_config = RAGConfig()
