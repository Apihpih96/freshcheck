import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
llm = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

for m in llm.models.list().data:
    print(m.id)