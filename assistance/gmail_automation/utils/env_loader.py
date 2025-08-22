import os
from dotenv import load_dotenv

def load_env():
    load_dotenv()
    return {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "GMAIL_EMAIL": os.getenv("GMAIL_EMAIL"),
        "GMAIL_PASSWORD": os.getenv("GMAIL_PASSWORD")
    }
