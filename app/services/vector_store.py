import os
import uuid
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.utils import embedding_functions
from app.utils.logging_config import logger
from app.utils.text_helpers import ensure_text

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "db/chroma")
COLLECTION_NAME = "research_knowledge"

# Use local sentence-transformer for embeddings
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Initialize client
os.makedirs(CHROMA_DB_PATH, exist_ok=True)
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

def get_or_create_collection():
    """Retrieve or create the ChromaDB collection."""
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function
    )

def chunk_text(text: Any, chunk_size: int = 800, chunk_overlap: int = 150) -> List[str]:
    """Split text into overlapping chunks."""
    text = ensure_text(text)
    if not text:
        return []
    
    words = text.split()
    chunks = []
    
    # Simple word-based chunking
    step = chunk_size - chunk_overlap
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk:
            chunks.append(chunk)
            
    return chunks

def add_document_content(session_id: str, file_name: str, content: str) -> int:
    """Chunk and add document text to the vector database."""
    collection = get_or_create_collection()
    chunks = chunk_text(content)
    
    if not chunks:
        logger.warning(f"VectorStore: No text extracted from {file_name}")
        return 0
        
    ids = [f"{session_id}_{file_name}_{i}_{uuid.uuid4().hex[:6]}" for i in range(len(chunks))]
    metadatas = [{"session_id": session_id, "file_name": file_name, "chunk_index": i} for i in range(len(chunks))]
    
    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )
    
    logger.info(f"VectorStore: Added {len(chunks)} chunks for {file_name} under session {session_id}")
    return len(chunks)

def similarity_search(query: str, session_id: Optional[str] = None, k: int = 4) -> List[Dict[str, Any]]:
    """
    Search ChromaDB for relevant document chunks.
    Filters by session_id if provided.
    """
    try:
        collection = get_or_create_collection()
        
        # Check if collection has items
        if collection.count() == 0:
            return []
            
        where = {"session_id": session_id} if session_id else None
        
        results = collection.query(
            query_texts=[query],
            n_results=k,
            where=where
        )
        
        formatted_results = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
            
            for doc, meta, dist in zip(docs, metas, distances):
                formatted_results.append({
                    "content": doc,
                    "metadata": meta,
                    "distance": float(dist)
                })
                
        return formatted_results
    except Exception as e:
        logger.error(f"VectorStore error during search: {e}", exc_info=True)
        return []
