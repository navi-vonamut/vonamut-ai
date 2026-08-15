import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings

api_key = os.getenv("GOOGLE_API_KEY", "")

models_to_test = [
    "models/text-embedding-004",
    "text-embedding-004",
    "models/embedding-001",
    "models/gemini-embedding-2"
]

for m in models_to_test:
    try:
        embedder = GoogleGenerativeAIEmbeddings(model=m, google_api_key=api_key)
        res = embedder.embed_query("Test sports news context")
        print(f"SUCCESS: Model '{m}' returned vector of length {len(res)}")
        break
    except Exception as e:
        print(f"FAILED: Model '{m}' -> {e}")
