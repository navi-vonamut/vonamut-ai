import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
from langchain_qdrant import QdrantVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings

def get_memory_store():
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))
    
    collection_name = "office_memory"
    
    # 1. Проверяем, существует ли коллекция
    if client.collection_exists(collection_name):
        # 2. Получаем информацию о коллекции
        collection_info = client.get_collection(collection_name)
        # 3. Проверяем размерность (у gemini-embedding-2 она 3072)
        # Если размерность не совпадает (например, осталась 768 от старых тестов), удаляем коллекцию
        if collection_info.config.params.vectors.size != 3072:
            print(f"Удаление старой коллекции {collection_name} из-за несовпадения размерности.")
            client.delete_collection(collection_name)

    # 4. Создаем коллекцию заново (если она была удалена или ее не было)
    if not client.collection_exists(collection_name):
        print(f"Создание новой коллекции {collection_name} с размерностью 3072.")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=3072, distance=models.Distance.COSINE),
        )
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-2")
    
    return QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embeddings
    )