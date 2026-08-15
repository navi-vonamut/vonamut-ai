import os
import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

async def test_gemini():
    api_key = os.getenv("GOOGLE_API_KEY", "")
    models = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]
    for m in models:
        try:
            print(f"Testing Gemini model: {m}...")
            llm = ChatGoogleGenerativeAI(model=m, google_api_key=api_key)
            res = await llm.ainvoke([HumanMessage(content="Say Hello in JSON format: {'msg': 'hello'}")])
            print(f"SUCCESS {m}: {res.content}")
            break
        except Exception as e:
            print(f"FAILED {m}: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
