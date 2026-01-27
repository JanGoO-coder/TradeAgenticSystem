"""
ChromaDB Vector Store Service.

Manages connections to ChromaDB for storing and querying strategy embeddings.
"""
import asyncio
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings


class VectorStoreService:
    """
    ChromaDB client for strategy storage and semantic search.

    Features:
    - Persistent connection to ChromaDB Docker container
    - Collection management for strategies
    - Async-compatible query interface
    - Health checking
    """

    def __init__(self):
        settings = get_settings()

        # Connect to ChromaDB server
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(
                anonymized_telemetry=False
            )
        )

        self._collections: dict = {}

    def get_or_create_collection(
        self,
        name: str,
        metadata: Optional[dict] = None
    ):
        """
        Get or create a collection by name.

        Args:
            name: Collection name
            metadata: Optional collection metadata

        Returns:
            ChromaDB collection
        """
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata=metadata or {"description": f"{name} collection"}
            )

        return self._collections[name]

    async def upsert_documents(
        self,
        collection_name: str,
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str]
    ):
        """
        Upsert documents with embeddings into a collection.

        Args:
            collection_name: Target collection
            documents: List of document texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts
            ids: List of unique document IDs
        """
        collection = self.get_or_create_collection(collection_name)

        # ChromaDB operations are sync, wrap in thread
        await asyncio.to_thread(
            collection.upsert,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        k: int = 5,
        where: Optional[dict] = None,
        include: list[str] = ["documents", "metadatas", "distances"]
    ) -> dict:
        """
        Query collection for similar documents.

        Args:
            collection_name: Collection to query
            query_embedding: Query vector
            k: Number of results
            where: Optional metadata filter
            include: Fields to include in results

        Returns:
            Query results with documents, metadatas, distances
        """
        collection = self.get_or_create_collection(collection_name)

        results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=k,
            where=where,
            include=include
        )

        return results

    async def get_by_id(
        self,
        collection_name: str,
        doc_id: str
    ) -> Optional[dict]:
        """
        Get a specific document by ID.

        Args:
            collection_name: Collection to query
            doc_id: Document ID

        Returns:
            Document with metadata or None
        """
        collection = self.get_or_create_collection(collection_name)

        results = await asyncio.to_thread(
            collection.get,
            ids=[doc_id],
            include=["documents", "metadatas"]
        )

        if results["ids"] and len(results["ids"]) > 0:
            return {
                "id": results["ids"][0],
                "document": results["documents"][0] if results["documents"] else None,
                "metadata": results["metadatas"][0] if results["metadatas"] else None
            }

        return None

    async def delete_collection(self, collection_name: str):
        """Delete a collection and all its documents."""
        await asyncio.to_thread(
            self.client.delete_collection,
            name=collection_name
        )

        if collection_name in self._collections:
            del self._collections[collection_name]

    async def list_collections(self) -> list[str]:
        """List all collection names."""
        collections = await asyncio.to_thread(self.client.list_collections)
        return [c.name for c in collections]

    async def get_collection_count(self, collection_name: str) -> int:
        """Get the number of documents in a collection."""
        collection = self.get_or_create_collection(collection_name)
        return await asyncio.to_thread(collection.count)

    async def health_check(self) -> dict:
        """
        Check ChromaDB connection health.

        Returns:
            {"healthy": bool, "message": str, "collections": int}
        """
        try:
            # Try to get heartbeat
            heartbeat = await asyncio.to_thread(self.client.heartbeat)
            collections = await self.list_collections()

            return {
                "healthy": True,
                "message": "ChromaDB connected",
                "heartbeat": heartbeat,
                "collections": len(collections)
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"ChromaDB error: {str(e)}",
                "collections": 0
            }


# Singleton instance
_vector_store: Optional[VectorStoreService] = None


async def get_vector_store() -> VectorStoreService:
    """Get or create the vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStoreService()
    return _vector_store
