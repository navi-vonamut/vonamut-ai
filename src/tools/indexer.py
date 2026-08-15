import os
import time
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.memory import get_memory_store

def index_multiple_repos(project_paths: list, project_id: str):
    print(f"🚀 Начинаем сборку знаний для проекта: {project_id}")
    all_docs = []
    
    # 1. Проходим по всем папкам
    for path in project_paths:
        if not os.path.exists(path):
            print(f"⚠️ Папка не найдена, пропускаем: {path}")
            continue
            
        print(f"🔍 Сканируем директорию: {path}...")
        loader = DirectoryLoader(
            path, 
            glob="**/*.md", 
            loader_cls=TextLoader,
            loader_kwargs={'autodetect_encoding': True}
        )
        docs = loader.load()
        all_docs.extend(docs)

    if not all_docs:
        print("❌ Маркдаун файлы не найдены ни в одной из папок!")
        return

    print(f"📄 Всего найдено файлов: {len(all_docs)}")
    
    # 2. Нарезаем на куски
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    chunks = text_splitter.split_documents(all_docs)
    
    # 3. Привязываем метаданные
    for chunk in chunks:
        chunk.metadata["project_id"] = project_id
        chunk.metadata["source_file"] = os.path.basename(chunk.metadata.get('source', 'unknown'))
    
    print(f"✂️ Файлы разбиты на {len(chunks)} фрагментов текста.")
    
# 4. УМНАЯ ЗАГРУЗКА (обход лимитов и защита от падений прокси)
    print("🧠 Подключаемся к API и векторной базе...")
    
    memory = None
    # Пытаемся подключиться 5 раз, если прокси сбрасывает соединение
    for attempt in range(5):
        try:
            memory = get_memory_store()
            break # Если успешно, выходим из цикла попыток
        except Exception as e:
            print(f"⚠️ Сетевой сбой Xray (попытка {attempt + 1}/5). Ждем 5 сек...")
            time.sleep(5)
            
    if not memory:
        print("❌ Прокси стабильно отклоняет запросы. Попробуй перезапустить Xray.")
        return
    
    batch_size = 10 
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        current_batch = (i // batch_size) + 1
        print(f"⏳ Загрузка порции {current_batch} из {total_batches}...")
        
        while True: 
            try:
                memory.add_documents(batch)
                print(f"✅ Порция {current_batch} загружена. Отдыхаем 15 секунд...")
                time.sleep(15) 
                break 
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"⚠️ Превышен лимит токенов (429)! Уходим в сон на 60 секунд...")
                    time.sleep(60)
                elif "104" in error_msg or "Connection" in error_msg:
                    print(f"⚠️ Прокси разорвал соединение. Повторяем отправку порции через 10 секунд...")
                    time.sleep(10)
                else:
                    print(f"❌ Неизвестная ошибка на порции {current_batch}: {e}")
                    break
    
    print(f"✅ Успех! Все {len(chunks)} фрагментов знаний загружены в мозг СЕО.")

if __name__ == "__main__":
    TARGET_PATHS = [
        "/app/projects/astro-docs/docs",       
        "/app/projects/astro-engine/docs", 
        "/app/projects/astro-guido/docs",  
        "/app/projects/astro-front/docs"   
    ]
    index_multiple_repos(TARGET_PATHS, "astroguido")