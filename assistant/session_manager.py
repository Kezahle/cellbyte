from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import json

from config.config import settings

@dataclass
class Artifact:
    """Represents a generated artifact (e.g., a chart or table)."""
    id: str
    type: str  # 'chart', 'table', 'file'
    format: str  # 'png', 'csv', etc.
    path: Path
    query: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the dataclass to a JSON-serializable dictionary."""
        d = asdict(self)
        d['path'] = str(self.path) # Convert Path object to string for JSON
        return d

@dataclass
class Interaction:
    """Represents a single user query and the assistant's response."""
    query: str
    plan: str
    code: str
    result_summary: str
    artifacts: List[str] = field(default_factory=list)  # List of Artifact IDs
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Converts the dataclass to a dictionary."""
        return asdict(self)

class SessionManager:
    """Manages the conversation history, artifacts, and session state."""

    def __init__(self):
        self.interactions: List[Interaction] = []
        self.artifacts: Dict[str, Artifact] = {}
        self._artifact_counter = 0

    def add_interaction(self, query: str, plan: str, code: str, result_summary: str, artifact_ids: Optional[List[str]] = None):
        """Adds a new interaction to the session history."""
        interaction = Interaction(
            query=query,
            plan=plan,
            code=code,
            result_summary=result_summary,
            artifacts=artifact_ids or []
        )
        self.interactions.append(interaction)

        # Trim history to the configured limit
        if len(self.interactions) > settings.HISTORY_LIMIT:
            self.interactions = self.interactions[-settings.HISTORY_LIMIT:]

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Returns the recent conversation history as a list of dictionaries,
        formatted for use in the LLM prompt.
        """
        return [interaction.to_dict() for interaction in self.interactions]

    def create_artifact(self, artifact_type: str, file_format: str, path: Path, query: str) -> Artifact:
        """Creates, registers, and returns a new artifact."""
        self._artifact_counter += 1
        artifact_id = f"{artifact_type}_{self._artifact_counter:03d}"
        
        artifact = Artifact(
            id=artifact_id,
            type=artifact_type,
            format=file_format,
            path=path,
            query=query,
            created_at=datetime.now().isoformat()
        )
        self.artifacts[artifact_id] = artifact
        return artifact

    def list_artifacts(self) -> List[Artifact]:
        """Returns a list of all artifacts in the current session."""
        return list(self.artifacts.values())

    def save_session(self, filepath: Path):
        """Saves the current session state to a JSON file."""
        session_data = {
            "interactions": [i.to_dict() for i in self.interactions],
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()},
            "saved_at": datetime.now().isoformat()
        }
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            raise IOError(f"Failed to save session to {filepath}. Error: {e}")

    def load_session(self, filepath: Path):
        """Loads a session state from a JSON file."""
        if not filepath.exists():
            raise FileNotFoundError(f"Session file not found: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.interactions = [Interaction(**i) for i in session_data.get("interactions", [])]
            
            self.artifacts = {}
            for artifact_id, artifact_data in session_data.get("artifacts", {}).items():
                # Important: Convert file path string back to a Path object
                artifact_data['path'] = Path(artifact_data['path'])
                self.artifacts[artifact_id] = Artifact(**artifact_data)
            
            # Restore the artifact counter to avoid ID collisions
            if self.artifacts:
                max_id = max([int(aid.split('_')[-1]) for aid in self.artifacts.keys()], default=0)
                self._artifact_counter = max_id
        except Exception as e:
            raise IOError(f"Failed to load or parse session file {filepath}. Error: {e}")