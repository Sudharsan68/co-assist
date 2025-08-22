from groq import Groq
import os 
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get('GROQ_API_KEY')
if not api_key:
    raise ValueError("GROQ_API_KEY environment variable not set!")
client = Groq(api_key=api_key)


def token(question, model, context):
    chat_completion = client.chat.completions.create(
    
    messages=[
    
        # Set an optional system message. This sets the behavior of the
        # assistant and can be used to provide specific instructions for
        # how it should behave throughout the conversation.
        {
            "role": "system",
            "content": "You are a helpful assistant. Answer the user's question based only on the provided context."
        },
        # Set a user message for the assistant to respond to.
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        }
    ],

    # The language model which will generate the completion.
    model="llama-3.3-70b-versatile"
    )
    return chat_completion.choices[0].message.content