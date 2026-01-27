"""
Persistence Service

Handles saving and loading of agent sessions to disk.
Uses atomic writes to prevent data corruption.
"""
import os
import json
import logging
import tempfile
import shutil
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class PersistenceManager:
    """
    Manages session persistence using JSON files.
    """

    def __init__(self, data_dir: str = "data/sessions"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session_id: str, state_dict: Dict[str, Any]) -> bool:
        """
        Save session state to disk using atomic write.
        
        Args:
            session_id: Unique session identifier
            state_dict: Dictionary containing serializable session state
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not session_id or not state_dict:
            return False

        file_path = self.data_dir / f"{session_id}.json"
        
        try:
            # Add metadata
            state_dict["_meta"] = {
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "version": "1.0.0"
            }

            # Atomic write: write to temp file then rename
            with tempfile.NamedTemporaryFile(mode='w', dir=self.data_dir, delete=False) as tf:
                json.dump(state_dict, tf, indent=2, default=str)
                temp_name = tf.name
            
            # Rename is atomic on POSIX, usually atomic on Windows (if dest exists, it might fail on older windows, but Python 3.8+ handles os.replace well)
            # shutil.move or os.replace
            os.replace(temp_name, file_path)
            
            logger.debug(f"Saved session {session_id} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            if 'temp_name' in locals() and os.path.exists(temp_name):
                os.remove(temp_name)
            return False

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load session state from disk.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            Dict or None if not found/error
        """
        file_path = self.data_dir / f"{session_id}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded session {session_id} from disk")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Corrupt session file {session_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    def list_sessions(self):
        """List all saved session IDs."""
        return [f.stem for f in self.data_dir.glob("*.json")]

    def delete_session(self, session_id: str):
        """Delete a saved session."""
        file_path = self.data_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()
