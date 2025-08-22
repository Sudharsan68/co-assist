#import necessary libraries
import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Qdrant
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings

# Load environment variables
load_dotenv()

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


##--------------------main porgram ------------------------------##


# Load the PDF file using PyPDFLoader   
loader = PyPDFLoader("SP39.pdf")

# Load the document from the loader
doc = loader.load()

# Use CharacterTextSplitter to split the document into chunks
text_splitter = CharacterTextSplitter(
    separator="\n\n",
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    is_separator_regex=False,
)

# Split the document into chunks
docs = text_splitter.split_documents(doc)

# Create a Qdrant vector store from the documents
try:
    qdrant = Qdrant.from_documents(
        docs,
        embeddings,
        collection_name="my_documents",
        url="https://9629e0dd-b11d-428c-a3d9-a5c7423e46cf.us-east4-0.gcp.cloud.qdrant.io",
        api_key = os.environ.get("QDRANT_API_KEY")
    )
    print("✅ Successfully uploaded documents to Qdrant!")
except Exception as e:
    print(f"❌ Error uploading to Qdrant: {e}")
    print("Please check your Qdrant cluster URL and API key permissions.")
