"""
Strategy Management API Endpoints.

Endpoints for managing trading strategies and rules in the vector store.
Allows adding, removing, listing, and searching strategies.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import os
import shutil

from app.core.config import get_settings
from app.services.strategy_store import get_strategy_store, reindex_strategies

router = APIRouter(prefix="/strategies", tags=["Strategy Management"])


# ============================================================================
# Request/Response Models
# ============================================================================

class StrategyFile(BaseModel):
    """Metadata about a strategy file."""
    filename: str
    path: str
    size_bytes: int
    modified_at: str
    rule_count: int = 0


class StrategyContent(BaseModel):
    """Content to add as a new strategy."""
    name: str = Field(..., description="Strategy name (used as filename)")
    content: str = Field(..., description="Markdown content of the strategy")
    description: Optional[str] = Field(None, description="Brief description")


class RuleInfo(BaseModel):
    """Information about a specific rule."""
    rule_id: str
    headers: str
    content: str
    source_file: str


class SearchResult(BaseModel):
    """Search result with relevance score."""
    content: str
    source: str
    headers: str
    rule_ids: List[str]
    score: float


# ============================================================================
# List and Get Strategies
# ============================================================================

@router.get("/files")
async def list_strategy_files() -> dict:
    """
    List all strategy files in the rules directory.

    Returns metadata about each .md file found.
    """
    settings = get_settings()
    strategies_path = Path(settings.strategies_dir)

    if not strategies_path.exists():
        strategies_path.mkdir(parents=True)
        return {"files": [], "total": 0}

    files = []
    for md_file in strategies_path.rglob("*.md"):
        stat = md_file.stat()

        # Count rules in file
        content = md_file.read_text(encoding="utf-8")
        import re
        rule_pattern = r'[Rr]ule\s+(\d+\.\d+(?:\.\d+)?)'
        rules = set(re.findall(rule_pattern, content))

        files.append(StrategyFile(
            filename=md_file.name,
            path=str(md_file.relative_to(strategies_path)),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            rule_count=len(rules)
        ))

    return {
        "files": [f.model_dump() for f in files],
        "total": len(files),
        "directory": str(strategies_path.absolute())
    }


@router.get("/file/{filename:path}")
async def get_strategy_file(filename: str) -> dict:
    """
    Get the content of a specific strategy file.
    """
    settings = get_settings()
    file_path = Path(settings.strategies_dir) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    if not file_path.suffix == ".md":
        raise HTTPException(status_code=400, detail="Only .md files are supported")

    content = file_path.read_text(encoding="utf-8")

    return {
        "filename": filename,
        "content": content,
        "size_bytes": len(content.encode("utf-8"))
    }


# ============================================================================
# Add Strategies
# ============================================================================

@router.post("/add")
async def add_strategy(strategy: StrategyContent) -> dict:
    """
    Add a new strategy from markdown content.

    Creates a new .md file and reindexes the vector store.
    """
    settings = get_settings()
    strategies_path = Path(settings.strategies_dir)
    strategies_path.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c for c in strategy.name if c.isalnum() or c in "._- ")
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    file_path = strategies_path / "rules" / safe_name
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if file_path.exists():
        raise HTTPException(status_code=400, detail=f"File already exists: {safe_name}")

    # Write content
    file_path.write_text(strategy.content, encoding="utf-8")

    # Reindex
    await reindex_strategies()

    return {
        "message": f"Strategy added: {safe_name}",
        "path": str(file_path.relative_to(strategies_path)),
        "indexed": True
    }


@router.post("/upload")
async def upload_strategy_file(
    file: UploadFile = File(...),
    subfolder: Optional[str] = Form(None)
) -> dict:
    """
    Upload a markdown strategy file.

    Accepts a .md file and stores it in the rules directory.
    """
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are accepted")

    settings = get_settings()
    strategies_path = Path(settings.strategies_dir)

    if subfolder:
        target_dir = strategies_path / subfolder
    else:
        target_dir = strategies_path / "rules"

    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file.filename

    # Write file
    content = await file.read()
    file_path.write_bytes(content)

    # Reindex
    await reindex_strategies()

    return {
        "message": f"File uploaded: {file.filename}",
        "path": str(file_path.relative_to(strategies_path)),
        "size_bytes": len(content),
        "indexed": True
    }


# ============================================================================
# Update Strategies
# ============================================================================

@router.put("/file/{filename:path}")
async def update_strategy_file(filename: str, content: str) -> dict:
    """
    Update the content of an existing strategy file.
    """
    settings = get_settings()
    file_path = Path(settings.strategies_dir) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    # Create backup
    backup_path = file_path.with_suffix(".md.bak")
    shutil.copy(file_path, backup_path)

    # Update content
    file_path.write_text(content, encoding="utf-8")

    # Reindex
    await reindex_strategies()

    return {
        "message": f"File updated: {filename}",
        "backup_created": str(backup_path.name),
        "indexed": True
    }


# ============================================================================
# Remove Strategies
# ============================================================================

@router.delete("/file/{filename:path}")
async def delete_strategy_file(filename: str, create_backup: bool = True) -> dict:
    """
    Delete a strategy file.

    Optionally creates a backup before deletion.
    """
    settings = get_settings()
    file_path = Path(settings.strategies_dir) / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    backup_path = None
    if create_backup:
        backup_dir = Path(settings.strategies_dir) / ".backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{file_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        shutil.copy(file_path, backup_path)

    file_path.unlink()

    # Reindex
    await reindex_strategies()

    return {
        "message": f"File deleted: {filename}",
        "backup_path": str(backup_path) if backup_path else None,
        "indexed": True
    }


# ============================================================================
# Search and Query
# ============================================================================

@router.get("/search")
async def search_strategies(
    query: str,
    limit: int = 5,
    rule_filter: Optional[str] = None
) -> dict:
    """
    Search strategies using semantic search.

    Args:
        query: Natural language query
        limit: Maximum number of results
        rule_filter: Comma-separated rule IDs to filter by
    """
    try:
        store = await get_strategy_store()

        rule_ids = None
        if rule_filter:
            rule_ids = [r.strip() for r in rule_filter.split(",")]

        results = await store.search_strategies(query, k=limit, rule_filter=rule_ids)

        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rule/{rule_id}")
async def get_rule(rule_id: str) -> dict:
    """
    Get a specific rule by ID (e.g., "6.5", "1.1").
    """
    try:
        store = await get_strategy_store()
        rule = await store.get_rule(rule_id)

        if not rule:
            raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")

        return {
            "rule_id": rule_id,
            **rule
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def list_all_rules() -> dict:
    """
    List all indexed rule IDs.
    """
    try:
        store = await get_strategy_store()
        rules = await store.list_all_rules()

        return {
            "rules": sorted(rules),
            "count": len(rules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Indexing Management
# ============================================================================

@router.post("/reindex")
async def trigger_reindex() -> dict:
    """
    Force reindex all strategy files.

    Use this after making manual changes to strategy files.
    """
    try:
        await reindex_strategies()

        store = await get_strategy_store()
        rules = await store.list_all_rules()

        return {
            "message": "Reindexing complete",
            "rules_indexed": len(rules),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/status")
async def get_index_status() -> dict:
    """
    Get the current status of the strategy index.
    """
    try:
        from app.services.vector_store import get_vector_store

        settings = get_settings()
        vector_store = await get_vector_store()

        # Check health
        health = await vector_store.health_check()

        # Get collection count
        try:
            count = await vector_store.get_collection_count(settings.strategy_collection)
        except Exception:
            count = 0

        # Count strategy files
        strategies_path = Path(settings.strategies_dir)
        file_count = len(list(strategies_path.rglob("*.md"))) if strategies_path.exists() else 0

        return {
            "vector_store": health,
            "collection": settings.strategy_collection,
            "chunks_indexed": count,
            "strategy_files": file_count,
            "strategies_dir": str(strategies_path.absolute())
        }
    except Exception as e:
        return {
            "error": str(e),
            "vector_store": {"healthy": False},
            "chunks_indexed": 0
        }
