"""
Aria — RAG Knowledge Base (ChromaDB + HuggingFace Embeddings).

Stores and retrieves loan policy information for the Loan Assistant persona.
The knowledge base is shared between web calls and phone calls.

Knowledge file: loan_policy.txt (at Aria project root level)
ChromaDB store: core/data/chroma/ (local, persistent)
"""

import os
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from commons.logger import logger

log = logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
# ChromaDB persisted at backend/core/data/chroma/
CHROMA_PERSIST_DIR = str(
    Path(__file__).resolve().parents[1] / "data" / "chroma"
)


class KnowledgeBase:
    def __init__(self):
        log.info("Initializing HuggingFace embeddings (all-MiniLM-L6-v2)...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        # Initialize ChromaDB vector store (local, persistent)
        try:
            os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
            self.vector_store = Chroma(
                persist_directory=CHROMA_PERSIST_DIR,
                embedding_function=self.embeddings,
                collection_name="loan_documents",
            )
            log.info(f"✅ Connected to ChromaDB at {CHROMA_PERSIST_DIR}")
        except Exception as e:
            log.error(f"❌ Failed to initialize ChromaDB: {e}")
            raise

    def add_document(self, file_path: str) -> int:
        """
        Process and add a document (PDF or .txt) to ChromaDB.
        Returns the number of chunks added.
        """
        try:
            log.info(f"Processing document: {file_path}")

            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                for doc in docs:
                    doc.metadata["parser"] = "pypdf"
            else:
                loader = TextLoader(file_path, encoding="utf-8")
                docs = loader.load()

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=200
            )
            chunks = splitter.split_documents(docs)
            log.info(f"Split into {len(chunks)} chunks")

            self.vector_store.add_documents(chunks)
            log.info("✅ Document added to Knowledge Base")
            return len(chunks)
        except Exception as e:
            log.error(f"Failed to add document: {e}")
            raise

    def query(self, query_text: str, k: int = 3) -> str:
        """Retrieve relevant context for a query via similarity search."""
        try:
            log.info(f"Querying Knowledge Base: {query_text}")
            results = self.vector_store.similarity_search(query_text, k=k)

            if not results:
                return "No relevant information found in the knowledge base."

            return "\n\n".join([doc.page_content for doc in results])
        except Exception as e:
            log.error(f"Failed to query knowledge base: {e}")
            return "Error retrieving information from the knowledge base."

    def clear(self):
        """Clear all documents from the knowledge base."""
        try:
            self.vector_store.delete_collection()
            self.vector_store = Chroma(
                persist_directory=CHROMA_PERSIST_DIR,
                embedding_function=self.embeddings,
                collection_name="loan_documents",
            )
            log.info("Knowledge Base cleared")
        except Exception as e:
            log.error(f"Failed to clear knowledge base: {e}")


# Singleton — shared by both web and phone call pipelines
kb = KnowledgeBase()
