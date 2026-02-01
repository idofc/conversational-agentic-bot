import os
from openai import OpenAI, AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Lazy initialization of client
_client = None
_provider = None

def _get_client():
    """Get or initialize OpenAI or Azure OpenAI client based on provider"""
    global _client, _provider
    if _client is None:
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        _provider = provider
        
        if provider == "azure":
            _client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
        else:
            _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    return _client

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    Generate embeddings for text using OpenAI or Azure OpenAI
    
    Args:
        text: Text to embed
        model: Model name for OpenAI, or deployment name for Azure
    """
    text = text.replace("\n", " ")
    client = _get_client()
    
    # For Azure, use deployment name from env if not provided
    if _provider == "azure":
        deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", model)
        response = client.embeddings.create(input=[text], model=deployment)
    else:
        response = client.embeddings.create(input=[text], model=model)
    
    return response.data[0].embedding
