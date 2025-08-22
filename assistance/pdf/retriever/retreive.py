
from langchain_qdrant import QdrantVectorStore

from langchain_community.embeddings import HuggingFaceEmbeddings
from pdf.retriever.llm import token
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

                                                                                                                                                                                                    

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

url = "https://9629e0dd-b11d-428c-a3d9-a5c7423e46cf.us-east4-0.gcp.cloud.qdrant.io"
api_key = os.environ.get("QDRANT_API_KEY")
 



qdrant = QdrantVectorStore.from_existing_collection(
    embedding=embeddings,
    collection_name="my_documents",
    url=url,
    api_key=api_key,
)

# Example usage without Streamlit:
def main():
    url = url
    question = input("Enter your question: ")
    chunks = qdrant.similarity_search(question, k=2)
    prompt = f"""
context :{chunks}

Question: {question}

anser the question based on the context.
"""
    print(prompt)
    ret = token(question, "x-ai/grok-2-vision-1212", url)
    print(ret)

if __name__ == "__main__":
    main()