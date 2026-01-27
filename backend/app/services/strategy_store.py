"""
Strategy Store - RAG over Markdown Strategy Files.

Loads, parses, embeds, and provides semantic search over trading strategies
defined in Markdown files. Strategies are indexed in ChromaDB for fast retrieval.
"""
import asyncio
import hashlib
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

from app.core.config import get_settings
from app.services.llm_service import get_gemini_service
from app.services.vector_store import get_vector_store, VectorStoreService


class StrategyChunk:
    """A chunk of strategy content with metadata."""

    def __init__(
        self,
        content: str,
        source_file: str,
        header_path: list[str],
        rule_ids: list[str],
        chunk_index: int
    ):
        self.content = content
        self.source_file = source_file
        self.header_path = header_path  # e.g., ["Rule 6.5", "Entry Conditions"]
        self.rule_ids = rule_ids
        self.chunk_index = chunk_index

        # Generate unique ID
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        self.id = f"{Path(source_file).stem}_{chunk_index}_{content_hash}"

    def to_metadata(self) -> dict:
        return {
            "source_file": self.source_file,
            "header_path": " > ".join(self.header_path),
            "rule_ids": ",".join(self.rule_ids) if self.rule_ids else "",
            "chunk_index": self.chunk_index
        }


class StrategyStore:
    """
    Manages strategy documents with semantic search capabilities.

    Features:
    - Scans rules/ directory for .md files
    - Parses by headers (##, ###) to create semantic chunks
    - Extracts rule IDs (e.g., "Rule 6.5", "6.1") for exact lookup
    - Embeds chunks via Gemini and stores in ChromaDB
    - Provides semantic search and exact rule lookup
    """

    def __init__(self):
        self.settings = get_settings()
        self.gemini = get_gemini_service()
        self.vector_store: Optional[VectorStoreService] = None

        self._indexed_files: dict[str, datetime] = {}
        self._chunks: list[StrategyChunk] = []
        self._rule_index: dict[str, list[StrategyChunk]] = {}  # rule_id -> chunks

    async def initialize(self):
        """
        Initialize the strategy store.

        Scans for .md files and indexes them if not already indexed.
        """
        # Get vector store (async)
        try:
            self.vector_store = await get_vector_store()
        except Exception as e:
            print(f"Warning: Could not connect to vector store: {e}")
            print("Running in fallback mode without vector embeddings")
            self.vector_store = None

        strategies_path = Path(self.settings.strategies_dir)

        if not strategies_path.exists():
            print(f"Strategies directory not found: {strategies_path}")
            # Create the directory
            strategies_path.mkdir(parents=True, exist_ok=True)
            return

        # Find all .md files
        md_files = list(strategies_path.rglob("*.md"))

        if not md_files:
            print(f"No .md files found in {strategies_path}")
            return

        print(f"Found {len(md_files)} strategy files")

        # Parse files to build local index regardless of vector store
        for md_file in md_files:
            chunks = self._parse_markdown_file(md_file)
            self._chunks.extend(chunks)
            self._indexed_files[str(md_file)] = datetime.now()

        self._build_rule_index()
        print(f"Loaded {len(self._chunks)} chunks with {len(self._rule_index)} rules from files")

        # If vector store available, check if we need to reindex
        if self.vector_store:
            try:
                collection_count = await self.vector_store.get_collection_count(
                    self.settings.strategy_collection
                )

                if collection_count == 0:
                    # Fresh index
                    await self.reindex_all()
                else:
                    print(f"Using existing index with {collection_count} chunks")
            except Exception as e:
                print(f"Error checking vector store: {e}")

    async def reindex_all(self):
        """
        Force reindex all strategy files.

        Clears existing collection and re-embeds all documents.
        """
        strategies_path = Path(self.settings.strategies_dir)
        md_files = list(strategies_path.rglob("*.md"))

        if not md_files:
            return

        print(f"Reindexing {len(md_files)} files...")

        # Parse all files first (always do this for local index)
        all_chunks: list[StrategyChunk] = []

        for md_file in md_files:
            chunks = self._parse_markdown_file(md_file)
            all_chunks.extend(chunks)
            self._indexed_files[str(md_file)] = datetime.now()

        self._chunks = all_chunks

        if not all_chunks:
            print("No chunks extracted from files")
            return

        # Build local rule index
        self._build_rule_index()
        print(f"Built local index with {len(all_chunks)} chunks")

        # If no vector store, skip embeddings
        if not self.vector_store:
            print("Vector store not available, using local index only")
            return

        # Clear existing collection
        try:
            await self.vector_store.delete_collection(self.settings.strategy_collection)
        except Exception:
            pass  # Collection may not exist

        print(f"Generating embeddings for {len(all_chunks)} chunks...")

        # Generate embeddings in batches
        batch_size = 20
        documents = [c.content for c in all_chunks]
        metadatas = [c.to_metadata() for c in all_chunks]
        ids = [c.id for c in all_chunks]

        all_embeddings = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            try:
                embeddings = await self.gemini.embed(batch)
                all_embeddings.extend(embeddings)
                print(f"  Embedded {min(i + batch_size, len(documents))}/{len(documents)}")
            except Exception as e:
                print(f"  Embedding error at batch {i}: {e}")
                # Use zero vectors as fallback
                for _ in batch:
                    all_embeddings.append([0.0] * 3072)

        # Store in ChromaDB
        try:
            await self.vector_store.upsert_documents(
                collection_name=self.settings.strategy_collection,
                documents=documents,
                embeddings=all_embeddings,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Indexed {len(all_chunks)} chunks with {len(self._rule_index)} unique rules")
        except Exception as e:
            print(f"Error storing in vector store: {e}")

    def _parse_markdown_file(self, file_path: Path) -> list[StrategyChunk]:
        """
        Parse a Markdown file into semantic chunks by headers.

        Chunks are created at ## and ### level, preserving hierarchy.
        """
        content = file_path.read_text(encoding="utf-8")
        chunks = []

        # Split by headers
        header_pattern = r'^(#{2,3})\s+(.+)$'
        lines = content.split('\n')

        current_chunk_lines = []
        current_headers = []
        chunk_index = 0

        for line in lines:
            header_match = re.match(header_pattern, line)

            if header_match:
                # Save previous chunk if exists
                if current_chunk_lines:
                    chunk_content = '\n'.join(current_chunk_lines).strip()
                    if len(chunk_content) > 50:  # Skip tiny chunks
                        rule_ids = self._extract_rule_ids(chunk_content)
                        chunks.append(StrategyChunk(
                            content=chunk_content,
                            source_file=str(file_path),
                            header_path=current_headers.copy(),
                            rule_ids=rule_ids,
                            chunk_index=chunk_index
                        ))
                        chunk_index += 1

                # Start new chunk
                level = len(header_match.group(1))
                header_text = header_match.group(2).strip()

                # Manage header hierarchy
                if level == 2:
                    current_headers = [header_text]
                elif level == 3:
                    if current_headers:
                        current_headers = [current_headers[0], header_text]
                    else:
                        current_headers = [header_text]

                current_chunk_lines = [line]
            else:
                current_chunk_lines.append(line)

        # Don't forget last chunk
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines).strip()
            if len(chunk_content) > 50:
                rule_ids = self._extract_rule_ids(chunk_content)
                chunks.append(StrategyChunk(
                    content=chunk_content,
                    source_file=str(file_path),
                    header_path=current_headers.copy(),
                    rule_ids=rule_ids,
                    chunk_index=chunk_index
                ))

        return chunks

    def _extract_rule_ids(self, text: str) -> list[str]:
        """
        Extract rule IDs from text (e.g., "Rule 6.5", "1.1", "Rule 2.3").
        """
        # Match patterns like "Rule 6.5", "rule 1.1", or standalone "6.5"
        patterns = [
            r'[Rr]ule\s+(\d+\.\d+(?:\.\d+)?)',  # "Rule 6.5" or "Rule 1.1.1"
            r'\b(\d+\.\d+(?:\.\d+)?)\b'           # Standalone "6.5"
        ]

        rule_ids = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            rule_ids.update(matches)

        return list(rule_ids)

    def _build_rule_index(self):
        """Build index from rule IDs to chunks."""
        self._rule_index = {}

        for chunk in self._chunks:
            for rule_id in chunk.rule_ids:
                if rule_id not in self._rule_index:
                    self._rule_index[rule_id] = []
                self._rule_index[rule_id].append(chunk)

    async def _load_rule_index(self):
        """Load rule index from stored chunks."""
        # Query all documents to rebuild local index
        # This is called when we're using existing ChromaDB data
        pass  # For now, require reindex if needed

    async def search_strategies(
        self,
        query: str,
        k: int = 5,
        rule_filter: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Semantic search for relevant strategy sections.

        Args:
            query: Natural language query or market state description
            k: Number of results to return
            rule_filter: Optional list of rule IDs to filter by

        Returns:
            List of {content, source, headers, rule_ids, score}
        """
        # If no vector store, fall back to local search
        if not self.vector_store:
            return self._local_search(query, k, rule_filter)

        try:
            # Generate query embedding
            query_embedding = await self.gemini.embed_query(query)

            # Build filter if specified
            where = None
            if rule_filter:
                # ChromaDB doesn't support OR on same field, so we search broader
                # and filter in Python
                pass

            # Query ChromaDB
            results = await self.vector_store.query(
                collection_name=self.settings.strategy_collection,
                query_embedding=query_embedding,
                k=k * 2 if rule_filter else k,  # Over-fetch if filtering
                include=["documents", "metadatas", "distances"]
            )

            # Format results
            formatted = []

            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    document = results["documents"][0][i] if results["documents"] else ""
                    distance = results["distances"][0][i] if results["distances"] else 1.0

                    # Filter by rule if specified
                    if rule_filter:
                        doc_rules = metadata.get("rule_ids", "").split(",")
                        if not any(r in doc_rules for r in rule_filter):
                            continue

                    formatted.append({
                        "content": document,
                        "source": metadata.get("source_file", "unknown"),
                        "headers": metadata.get("header_path", ""),
                        "rule_ids": metadata.get("rule_ids", "").split(","),
                        "score": 1 - distance  # Convert distance to similarity
                    })

                    if len(formatted) >= k:
                        break

            return formatted
        except Exception as e:
            print(f"Vector search error, falling back to local: {e}")
            return self._local_search(query, k, rule_filter)

    def _local_search(
        self,
        query: str,
        k: int = 5,
        rule_filter: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Simple keyword-based local search when vector store is unavailable.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_chunks = []
        for chunk in self._chunks:
            # Filter by rule if specified
            if rule_filter:
                if not any(r in chunk.rule_ids for r in rule_filter):
                    continue

            # Simple keyword matching score
            content_lower = chunk.content.lower()
            score = sum(1 for word in query_words if word in content_lower)

            if score > 0:
                scored_chunks.append((chunk, score))

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        # Return top k
        results = []
        for chunk, score in scored_chunks[:k]:
            results.append({
                "content": chunk.content,
                "source": chunk.source_file,
                "headers": " > ".join(chunk.header_path),
                "rule_ids": chunk.rule_ids,
                "score": score / len(query_words) if query_words else 0
            })

        return results

    async def get_rule(self, rule_id: str) -> Optional[dict]:
        """
        Get a specific rule by ID (exact match).

        Args:
            rule_id: Rule ID like "6.5" or "1.1"

        Returns:
            {content, source, headers} or None
        """
        # Check local index first
        if rule_id in self._rule_index:
            chunks = self._rule_index[rule_id]
            if chunks:
                chunk = chunks[0]
                return {
                    "content": chunk.content,
                    "source": chunk.source_file,
                    "headers": " > ".join(chunk.header_path),
                    "rule_ids": chunk.rule_ids
                }

        # Fall back to semantic search
        results = await self.search_strategies(
            f"Rule {rule_id}",
            k=1,
            rule_filter=[rule_id]
        )

        return results[0] if results else None

    async def list_all_rules(self) -> list[str]:
        """Get list of all indexed rule IDs."""
        return list(self._rule_index.keys())

    async def get_strategies_for_context(
        self,
        market_summary: str,
        k: int = 3
    ) -> str:
        """
        Get relevant strategy context for the agent.

        Returns formatted string of strategy sections for prompt injection.
        """
        results = await self.search_strategies(market_summary, k=k)

        if not results:
            return "No specific strategies found for current context."

        sections = []
        for r in results:
            header = r["headers"] if r["headers"] else "Strategy Section"
            sections.append(f"### {header}\n{r['content']}")

        return "\n\n---\n\n".join(sections)


# Singleton instance
_strategy_store: Optional[StrategyStore] = None


async def get_strategy_store() -> StrategyStore:
    """Get or create the strategy store singleton."""
    global _strategy_store
    if _strategy_store is None:
        _strategy_store = StrategyStore()
        await _strategy_store.initialize()
    return _strategy_store


async def reindex_strategies():
    """Force reindex all strategies."""
    store = await get_strategy_store()
    await store.reindex_all()
