"""
Version Control System for QBD Designs

Provides branching, forking, merging, and locking for design states.
Treats designs like code — versioned, diffable, collaborative.
"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import hashlib
import json
from collections import defaultdict


# =============================================================================
# VERSION TYPES
# =============================================================================

class VersionState(Enum):
    """Lifecycle states for a version."""
    DRAFT = "draft"           # Active editing
    SOLVED = "solved"         # Layout generated, may edit
    LOCKED = "locked"         # Immutable (construction docs issued)
    ARCHIVED = "archived"     # Old, kept for reference


class BranchType(Enum):
    """Types of branches."""
    MAIN = "main"             # Primary design line
    EXPLORATION = "exploration"  # Design alternatives
    CLIENT_REVIEW = "client_review"  # For client feedback
    REGULATORY = "regulatory"  # Code compliance variants


# =============================================================================
# VERSION NODE
# =============================================================================

@dataclass
class VersionNode:
    """
    A single version in the design history.
    
    Immutable once created — changes create new versions.
    """
    
    # Identity
    id: str
    branch_id: str
    parent_id: Optional[str]
    
    # Content
    state_snapshot: Dict[str, Any]  # Serialized design state
    layout_data: Optional[Dict] = None  # Generated layout if solved
    
    # Metadata
    author: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""  # Commit message
    
    # Status
    state: VersionState = VersionState.DRAFT
    
    # Derived data (computed on creation)
    hash: str = ""  # Content hash for integrity
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute content hash for integrity checking."""
        content = json.dumps(self.state_snapshot, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "branch_id": self.branch_id,
            "parent_id": self.parent_id,
            "hash": self.hash,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "state": self.state.value,
            "has_layout": self.layout_data is not None
        }


# =============================================================================
# BRANCH
# =============================================================================

@dataclass
class Branch:
    """A line of design development."""
    
    id: str
    name: str
    type: BranchType
    
    # Version chain
    head_version_id: str  # Latest version on this branch
    root_version_id: str  # First version on this branch
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = ""
    
    # Merge tracking
    merged_from: Optional[str] = None  # Branch this was merged from
    merged_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "head": self.head_version_id,
            "root": self.root_version_id,
            "created": self.created_at.isoformat(),
            "merged_from": self.merged_from
        }


# =============================================================================
# DESIGN HISTORY (VERSION GRAPH)
# =============================================================================

class DesignHistory:
    """
    Complete version history for a design project.
    
    Manages the DAG of versions across branches.
    """
    
    def __init__(self, project_id: str, project_name: str = ""):
        self.project_id = project_id
        self.project_name = project_name
        
        # Storage
        self.versions: Dict[str, VersionNode] = {}
        self.branches: Dict[str, Branch] = {}
        
        # Current position
        self.current_branch_id: Optional[str] = None
        self.current_version_id: Optional[str] = None
        
        # Initialize with main branch
        self._init_main_branch()
    
    def _init_main_branch(self):
        """Create initial main branch."""
        main_branch = Branch(
            id="main",
            name="Main Design",
            type=BranchType.MAIN,
            head_version_id="",
            root_version_id=""
        )
        
        # Create empty root version
        root_version = VersionNode(
            id=self._generate_id(),
            branch_id="main",
            parent_id=None,
            state_snapshot={"lifecycle": "EMPTY"},
            message="Initial empty design"
        )
        
        main_branch.root_version_id = root_version.id
        main_branch.head_version_id = root_version.id
        
        self.versions[root_version.id] = root_version
        self.branches["main"] = main_branch
        
        self.current_branch_id = "main"
        self.current_version_id = root_version.id
    
    def _generate_id(self) -> str:
        """Generate unique version ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = hashlib.sha256(
            str(datetime.now().timestamp()).encode()
        ).hexdigest()[:6]
        return f"v{timestamp}-{random_suffix}"
    
    # =========================================================================
    # CORE OPERATIONS
    # =========================================================================
    
    def commit(
        self,
        state_snapshot: Dict[str, Any],
        message: str,
        author: str = "",
        layout_data: Optional[Dict] = None
    ) -> str:
        """
        Create a new version from current state.
        
        Returns:
            New version ID
        """
        if not self.current_branch_id:
            raise ValueError("No current branch")
        
        branch = self.branches[self.current_branch_id]
        
        # Create new version
        version = VersionNode(
            id=self._generate_id(),
            branch_id=self.current_branch_id,
            parent_id=self.current_version_id,
            state_snapshot=state_snapshot,
            layout_data=layout_data,
            author=author,
            message=message
        )
        
        # Update branch head
        branch.head_version_id = version.id
        
        # Store
        self.versions[version.id] = version
        self.current_version_id = version.id
        
        return version.id
    
    def fork(
        self,
        branch_name: str,
        branch_type: BranchType = BranchType.EXPLORATION,
        from_version: Optional[str] = None,
        author: str = ""
    ) -> str:
        """
        Create a new branch from a version.
        
        Returns:
            New branch ID
        """
        source_version_id = from_version or self.current_version_id
        source_version = self.versions.get(source_version_id)
        
        if not source_version:
            raise ValueError(f"Source version not found: {source_version_id}")
        
        # Create branch
        branch_id = f"branch-{self._generate_id()}"
        branch = Branch(
            id=branch_id,
            name=branch_name,
            type=branch_type,
            head_version_id=source_version_id,
            root_version_id=source_version_id,
            created_by=author
        )
        
        self.branches[branch_id] = branch
        
        # Switch to new branch
        self.current_branch_id = branch_id
        self.current_version_id = source_version_id
        
        return branch_id
    
    def switch_branch(self, branch_id: str, version_id: Optional[str] = None):
        """Switch to a different branch/version."""
        if branch_id not in self.branches:
            raise ValueError(f"Branch not found: {branch_id}")
        
        branch = self.branches[branch_id]
        
        self.current_branch_id = branch_id
        
        if version_id:
            if version_id not in self.versions:
                raise ValueError(f"Version not found: {version_id}")
            self.current_version_id = version_id
        else:
            self.current_version_id = branch.head_version_id
    
    def lock(self, version_id: Optional[str] = None, message: str = ""):
        """
        Lock a version — mark as immutable.
        
        This is like issuing construction documents.
        Changes require creating a new branch.
        """
        vid = version_id or self.current_version_id
        version = self.versions.get(vid)
        
        if not version:
            raise ValueError(f"Version not found: {vid}")
        
        if version.state == VersionState.LOCKED:
            raise ValueError(f"Version already locked: {vid}")
        
        version.state = VersionState.LOCKED
        version.message = f"{version.message} [LOCKED: {message}]"
    
    def unlock(self, version_id: Optional[str] = None, author: str = "") -> str:
        """
        Unlock a version — creates new branch for editing.
        
        Returns:
            New branch ID
        """
        vid = version_id or self.current_version_id
        version = self.versions.get(vid)
        
        if not version:
            raise ValueError(f"Version not found: {vid}")
        
        # Create new branch from locked version
        branch_id = self.fork(
            branch_name=f"Edit from {vid[:8]}",
            branch_type=BranchType.EXPLORATION,
            from_version=vid,
            author=author
        )
        
        return branch_id
    
    # =========================================================================
    # MERGE
    # =========================================================================
    
    def merge(
        self,
        source_branch_id: str,
        target_branch_id: Optional[str] = None,
        author: str = "",
        message: str = ""
    ) -> Tuple[str, List[Dict]]:
        """
        Merge one branch into another.
        
        Returns:
            (new_version_id, list_of_conflicts)
        """
        target = target_branch_id or self.current_branch_id
        
        if source_branch_id not in self.branches:
            raise ValueError(f"Source branch not found: {source_branch_id}")
        if target not in self.branches:
            raise ValueError(f"Target branch not found: {target}")
        
        source_branch = self.branches[source_branch_id]
        target_branch = self.branches[target]
        
        # Get versions to merge
        source_version = self.versions[source_branch.head_version_id]
        target_version = self.versions[target_branch.head_version_id]
        
        # Find common ancestor
        ancestor_id = self._find_common_ancestor(
            source_branch.head_version_id,
            target_branch.head_version_id
        )
        
        # Compute diff
        source_changes = self._diff(ancestor_id, source_branch.head_version_id)
        target_changes = self._diff(ancestor_id, target_branch.head_version_id)
        
        # Detect conflicts
        conflicts = self._detect_merge_conflicts(source_changes, target_changes)
        
        if conflicts:
            # Return conflicts for resolution
            return None, conflicts
        
        # Apply merged changes
        merged_state = self._apply_merge(
            target_version.state_snapshot,
            source_changes,
            target_changes
        )
        
        # Create merge commit
        merge_version = VersionNode(
            id=self._generate_id(),
            branch_id=target,
            parent_id=target_branch.head_version_id,
            state_snapshot=merged_state,
            author=author,
            message=f"Merge {source_branch_id}: {message}"
        )
        
        # Mark as merge
        source_branch.merged_from = source_branch_id
        source_branch.merged_at = datetime.now()
        
        # Update target branch
        target_branch.head_version_id = merge_version.id
        
        # Store
        self.versions[merge_version.id] = merge_version
        self.current_version_id = merge_version.id
        self.current_branch_id = target
        
        return merge_version.id, []
    
    def _find_common_ancestor(self, v1_id: str, v2_id: str) -> Optional[str]:
        """Find the common ancestor of two versions."""
        # Build ancestor chain for v1
        v1_ancestors = set()
        current = v1_id
        while current:
            v1_ancestors.add(current)
            version = self.versions.get(current)
            current = version.parent_id if version else None
        
        # Walk back from v2 until we hit common ancestor
        current = v2_id
        while current:
            if current in v1_ancestors:
                return current
            version = self.versions.get(current)
            current = version.parent_id if version else None
        
        return None
    
    def _detect_merge_conflicts(
        self,
        source_changes: List[Dict],
        target_changes: List[Dict]
    ) -> List[Dict]:
        """Detect conflicts between two change sets."""
        conflicts = []
        
        # Index by target
        source_by_target = {c["target"]: c for c in source_changes}
        target_by_target = {c["target"]: c for c in target_changes}
        
        # Find overlapping changes
        for target in set(source_by_target.keys()) & set(target_by_target.keys()):
            s_change = source_by_target[target]
            t_change = target_by_target[target]
            
            # Conflict if both changed the same property differently
            if s_change.get("value") != t_change.get("value"):
                conflicts.append({
                    "target": target,
                    "source_value": s_change.get("value"),
                    "target_value": t_change.get("value"),
                    "source_fragment": s_change.get("fragment"),
                    "target_fragment": t_change.get("fragment")
                })
        
        return conflicts
    
    def _apply_merge(
        self,
        base_state: Dict,
        source_changes: List[Dict],
        target_changes: List[Dict]
    ) -> Dict:
        """Apply merged changes to base state."""
        # Start with base
        merged = json.loads(json.dumps(base_state))  # Deep copy
        
        # Apply target changes (current branch)
        for change in target_changes:
            self._apply_change(merged, change)
        
        # Apply source changes (merging branch)
        for change in source_changes:
            self._apply_change(merged, change)
        
        return merged
    
    def _apply_change(self, state: Dict, change: Dict):
        """Apply a single change to state."""
        target = change["target"]
        value = change["value"]
        
        # Navigate to target property
        parts = target.split(".")
        current = state
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set value
        current[parts[-1]] = value
    
    # =========================================================================
    # DIFF
    # =========================================================================
    
    def diff(self, v1_id: str, v2_id: str) -> List[Dict]:
        """
        Compute difference between two versions.
        
        Returns:
            List of changes (fragments) to transform v1 into v2
        """
        return self._diff(v1_id, v2_id)
    
    def _diff(self, v1_id: str, v2_id: str) -> List[Dict]:
        """Internal diff implementation."""
        v1 = self.versions.get(v1_id)
        v2 = self.versions.get(v2_id)
        
        if not v1 or not v2:
            raise ValueError("Version not found")
        
        changes = []
        
        # Simple dict diff
        s1 = v1.state_snapshot
        s2 = v2.state_snapshot
        
        def compare_dicts(d1: Dict, d2: Dict, path: str = ""):
            all_keys = set(d1.keys()) | set(d2.keys())
            
            for key in all_keys:
                current_path = f"{path}.{key}" if path else key
                
                if key not in d1:
                    # Added in v2
                    changes.append({
                        "action": "add",
                        "target": current_path,
                        "value": d2[key],
                        "fragment": f"add_{current_path.replace('.', '_')}"
                    })
                elif key not in d2:
                    # Removed in v2
                    changes.append({
                        "action": "remove",
                        "target": current_path,
                        "value": d1[key],
                        "fragment": f"remove_{current_path.replace('.', '_')}"
                    })
                elif isinstance(d1[key], dict) and isinstance(d2[key], dict):
                    # Recurse
                    compare_dicts(d1[key], d2[key], current_path)
                elif d1[key] != d2[key]:
                    # Changed
                    changes.append({
                        "action": "update",
                        "target": current_path,
                        "old_value": d1[key],
                        "value": d2[key],
                        "fragment": f"update_{current_path.replace('.', '_')}"
                    })
        
        compare_dicts(s1, s2)
        
        return changes
    
    # =========================================================================
    # QUERY
    # =========================================================================
    
    def get_version_history(
        self,
        branch_id: Optional[str] = None,
        limit: int = 50
    ) -> List[VersionNode]:
        """Get version history for a branch."""
        bid = branch_id or self.current_branch_id
        branch = self.branches.get(bid)
        
        if not branch:
            return []
        
        # Walk back from head
        history = []
        current_id = branch.head_version_id
        
        while current_id and len(history) < limit:
            version = self.versions.get(current_id)
            if not version:
                break
            
            history.append(version)
            
            # Stop at branch root unless it's main
            if current_id == branch.root_version_id and bid != "main":
                break
            
            current_id = version.parent_id
        
        return history
    
    def get_branch_tree(self) -> Dict:
        """Get tree structure of all branches."""
        tree = {
            "main": {
                "branch": self.branches["main"].to_dict(),
                "versions": []
            }
        }
        
        # Add main branch versions
        main_history = self.get_version_history("main", limit=1000)
        tree["main"]["versions"] = [v.to_dict() for v in main_history]
        
        # Add other branches
        for branch_id, branch in self.branches.items():
            if branch_id == "main":
                continue
            
            tree[branch_id] = {
                "branch": branch.to_dict(),
                "versions": [
                    v.to_dict() for v in self.get_version_history(branch_id, limit=100)
                ]
            }
        
        return tree
    
    def compare_branches(
        self,
        branch1_id: str,
        branch2_id: str
    ) -> Dict:
        """Compare two branches."""
        b1 = self.branches.get(branch1_id)
        b2 = self.branches.get(branch2_id)
        
        if not b1 or not b2:
            raise ValueError("Branch not found")
        
        v1 = self.versions[b1.head_version_id]
        v2 = self.versions[b2.head_version_id]
        
        changes = self._diff(b1.head_version_id, b2.head_version_id)
        
        return {
            "branch1": branch1_id,
            "branch2": branch2_id,
            "versions": {
                "v1": v1.to_dict(),
                "v2": v2.to_dict()
            },
            "changes": changes,
            "change_count": len(changes)
        }
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def to_dict(self) -> Dict:
        """Serialize entire history."""
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "current_branch": self.current_branch_id,
            "current_version": self.current_version_id,
            "branches": {k: v.to_dict() for k, v in self.branches.items()},
            "versions": {k: v.to_dict() for k, v in self.versions.items()},
            "version_count": len(self.versions)
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DesignHistory':
        """Deserialize history."""
        history = cls(
            project_id=data["project_id"],
            project_name=data.get("project_name", "")
        )
        
        # Restore versions
        for vid, vdata in data.get("versions", {}).items():
            version = VersionNode(
                id=vdata["id"],
                branch_id=vdata["branch_id"],
                parent_id=vdata.get("parent_id"),
                hash=vdata.get("hash", ""),
                author=vdata.get("author", ""),
                timestamp=datetime.fromisoformat(vdata["timestamp"]),
                message=vdata.get("message", ""),
                state=VersionState(vdata.get("state", "draft")),
                state_snapshot={},  # Would need full snapshot storage
                layout_data=None
            )
            history.versions[vid] = version
        
        # Restore branches
        for bid, bdata in data.get("branches", {}).items():
            branch = Branch(
                id=bdata["id"],
                name=bdata["name"],
                type=BranchType(bdata["type"]),
                head_version_id=bdata["head"],
                root_version_id=bdata["root"],
                created_at=datetime.fromisoformat(bdata["created"]),
                created_by=bdata.get("created_by", ""),
                merged_from=bdata.get("merged_from")
            )
            if bdata.get("merged_at"):
                branch.merged_at = datetime.fromisoformat(bdata["merged_at"])
            history.branches[bid] = branch
        
        # Restore current position
        history.current_branch_id = data.get("current_branch")
        history.current_version_id = data.get("current_version")
        
        return history


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_design_history(project_id: str, project_name: str = "") -> DesignHistory:
    """Create new design history."""
    return DesignHistory(project_id, project_name)


def fork_for_exploration(
    history: DesignHistory,
    exploration_name: str,
    author: str = ""
) -> str:
    """Fork current state for design exploration."""
    return history.fork(
        branch_name=exploration_name,
        branch_type=BranchType.EXPLORATION,
        author=author
    )


def lock_for_construction(
    history: DesignHistory,
    version_id: Optional[str] = None,
    permit_number: str = ""
) -> str:
    """Lock version for construction (like issuing permit drawings)."""
    history.lock(
        version_id=version_id,
        message=f"Construction documents issued. Permit: {permit_number}"
    )
    return history.current_version_id


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VERSION CONTROL SYSTEM TEST")
    print("=" * 60)
    
    # Create history
    history = create_design_history("proj-001", "Test House")
    
    print("\n--- Initial State ---")
    print(f"Current branch: {history.current_branch_id}")
    print(f"Current version: {history.current_version_id[:20]}...")
    
    # Make some commits
    print("\n--- Commits ---")
    v1 = history.commit(
        state_snapshot={"rooms": ["living", "kitchen"], "sqft": 1000},
        message="Initial design",
        author="Alice"
    )
    print(f"Commit 1: {v1[:20]}... - Initial design")
    
    v2 = history.commit(
        state_snapshot={"rooms": ["living", "kitchen", "bedroom"], "sqft": 1500},
        message="Added bedroom",
        author="Alice"
    )
    print(f"Commit 2: {v2[:20]}... - Added bedroom")
    
    v3 = history.commit(
        state_snapshot={"rooms": ["living", "kitchen", "bedroom", "bath"], "sqft": 1800},
        message="Added bathroom",
        author="Bob"
    )
    print(f"Commit 3: {v3[:20]}... - Added bathroom")
    
    # Fork for exploration
    print("\n--- Fork ---")
    alt_branch = history.fork(
        branch_name="Two-story alternative",
        branch_type=BranchType.EXPLORATION,
        author="Alice"
    )
    print(f"Forked to branch: {alt_branch}")
    
    # Commit on new branch
    v4 = history.commit(
        state_snapshot={
            "rooms": ["living", "kitchen", "bedroom", "bath", "bedroom2"],
            "sqft": 2200,
            "stories": 2
        },
        message="Added second floor bedroom",
        author="Alice"
    )
    print(f"Commit 4 (alt): {v4[:20]}... - Added second floor")
    
    # Switch back to main
    print("\n--- Switch Branch ---")
    history.switch_branch("main")
    print(f"Switched to main, version: {history.current_version_id[:20]}...")
    
    # Commit on main
    v5 = history.commit(
        state_snapshot={
            "rooms": ["living", "kitchen", "bedroom", "bath", "garage"],
            "sqft": 2000
        },
        message="Added garage",
        author="Bob"
    )
    print(f"Commit 5 (main): {v5[:20]}... - Added garage")
    
    # Diff
    print("\n--- Diff ---")
    changes = history.diff(v3, v5)
    print(f"Changes from v3 to v5: {len(changes)}")
    for c in changes:
        print(f"  {c['action']}: {c['target']}")
    
    # Branch tree
    print("\n--- Branch Tree ---")
    tree = history.get_branch_tree()
    for branch_id, data in tree.items():
        print(f"\n{branch_id}:")
        print(f"  Head: {data['branch']['head'][:20]}...")
        print(f"  Versions: {len(data['versions'])}")
    
    # Lock
    print("\n--- Lock ---")
    history.lock(message="Permit APP-2024-001")
    print(f"Locked version: {history.current_version_id[:20]}...")
    print(f"State: {history.versions[history.current_version_id].state.value}")
    
    # Try to unlock (creates new branch)
    print("\n--- Unlock (Edit Branch) ---")
    edit_branch = history.unlock(author="Alice")
    print(f"Created edit branch: {history.current_branch_id}")
    
    # History
    print("\n--- Version History (Main) ---")
    main_history = history.get_version_history("main")
    for v in main_history:
        print(f"  {v.id[:20]}... - {v.message} ({v.author})")
    
    # Serialize
    print("\n--- Serialization ---")
    data = history.to_dict()
    print(f"Project: {data['project_name']}")
    print(f"Branches: {len(data['branches'])}")
    print(f"Total versions: {data['version_count']}")
