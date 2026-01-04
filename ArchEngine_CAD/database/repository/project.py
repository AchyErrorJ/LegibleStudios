"""
Project repository for project-specific database operations.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.project import Project, ProjectVersion
from database.repository.base import BaseRepository, AsyncBaseRepository


class ProjectRepository(BaseRepository[Project]):
    """
    Repository for Project entities with project-specific queries.
    """

    def __init__(self, session: Session):
        super().__init__(Project, session)

    def get_by_workspace(
        self,
        workspace_id: str,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Project]:
        """Get all projects in a workspace."""
        query = self.session.query(Project).filter(
            Project.workspace_id == workspace_id
        )

        if not include_deleted:
            query = query.filter(Project.deleted_at.is_(None))

        return query.order_by(Project.updated_at.desc()).offset(skip).limit(limit).all()

    def get_with_elements(self, id: str) -> Optional[Project]:
        """Get project with all building elements loaded."""
        return self.session.query(Project).options(
            joinedload(Project.walls),
            joinedload(Project.doors),
            joinedload(Project.windows),
            joinedload(Project.rooms),
            joinedload(Project.wall_types),
            joinedload(Project.roofs),
            joinedload(Project.sheets),
        ).filter(Project.id == id).first()

    def get_by_name(self, workspace_id: str, name: str) -> Optional[Project]:
        """Find project by name within a workspace."""
        return self.session.query(Project).filter(
            and_(
                Project.workspace_id == workspace_id,
                Project.name == name,
                Project.deleted_at.is_(None)
            )
        ).first()

    def search(
        self,
        workspace_id: str,
        query: str,
        limit: int = 20
    ) -> List[Project]:
        """Search projects by name or building type."""
        return self.session.query(Project).filter(
            and_(
                Project.workspace_id == workspace_id,
                Project.deleted_at.is_(None),
                Project.name.ilike(f"%{query}%")
            )
        ).limit(limit).all()

    def export_to_dict(self, project: Project) -> Dict[str, Any]:
        """Export project with all elements to legacy JSON format."""
        # Load all relationships if not already loaded
        if not self.session.object_session(project):
            project = self.get_with_elements(project.id)

        return project.to_legacy_dict() if project else {}

    def import_from_dict(
        self,
        data: Dict[str, Any],
        workspace_id: str
    ) -> Project:
        """Create project from legacy JSON format."""
        from database.models.building import Wall, Door, Window, Room, WallType, Roof

        # Create project
        project = Project(
            workspace_id=workspace_id,
            name=data.get("name", "Imported Project"),
            building_type=data.get("building_type", "residential"),
            width=data.get("width", 12000),
            depth=data.get("depth", 10000),
            stories=data.get("stories", 1),
            wall_height=data.get("wall_height", 2700),
            qbd_answers=data.get("qbd_answers", {}),
            settings=data.get("settings", {}),
        )
        self.session.add(project)
        self.session.flush()

        # Import wall types
        for wt_data in data.get("wall_types", {}).values():
            wt = WallType(
                project_id=project.id,
                type_key=wt_data.get("id", ""),
                name=wt_data.get("name", ""),
                thickness=wt_data.get("thickness", 140),
                layers=wt_data.get("layers", []),
            )
            self.session.add(wt)

        # Import walls
        wall_map = {}  # old index -> new id
        for wall_data in data.get("walls_batch", []):
            wall = Wall(
                project_id=project.id,
                index=wall_data.get("index", 0),
                start_x=wall_data["start"][0],
                start_y=wall_data["start"][1],
                start_z=wall_data["start"][2],
                end_x=wall_data["end"][0],
                end_y=wall_data["end"][1],
                end_z=wall_data["end"][2],
                height=wall_data.get("height", 2700),
                category=wall_data.get("category", "exterior"),
                wall_type_id=None,  # Link later if needed
                is_pinned=wall_data.get("is_pinned", False),
            )
            self.session.add(wall)
            self.session.flush()
            wall_map[wall_data.get("index", 0)] = wall.id

        # Import doors
        for door_data in data.get("doors", []):
            door = Door(
                project_id=project.id,
                wall_id=wall_map.get(door_data.get("wall_index")),
                offset=door_data.get("offset", 500),
                width=door_data.get("width", 900),
                height=door_data.get("height", 2100),
                door_type=door_data.get("type", "single"),
                swing=door_data.get("swing", "left"),
            )
            self.session.add(door)

        # Import windows
        for win_data in data.get("windows", []):
            window = Window(
                project_id=project.id,
                wall_id=wall_map.get(win_data.get("wall_index")),
                offset=win_data.get("offset", 500),
                width=win_data.get("width", 1200),
                height=win_data.get("height", 1200),
                sill_height=win_data.get("sill_height", 900),
            )
            self.session.add(window)

        # Import rooms
        for room_key, room_data in data.get("rooms", {}).items():
            room = Room(
                project_id=project.id,
                room_key=room_key,
                name=room_data.get("name", room_key),
                room_type=room_data.get("type", "other"),
                bounds=room_data.get("bounds", {}),
                area=room_data.get("area", 0),
            )
            self.session.add(room)

        # Import roofs
        for roof_data in data.get("roofs", []):
            roof = Roof(
                project_id=project.id,
                roof_type=roof_data.get("type", "gable"),
                pitch=roof_data.get("pitch", 6),
                surfaces=roof_data.get("surfaces", []),
                framing=roof_data.get("framing", {}),
            )
            self.session.add(roof)

        self.session.flush()
        return project


class ProjectVersionRepository(BaseRepository[ProjectVersion]):
    """Repository for project version history."""

    def __init__(self, session: Session):
        super().__init__(ProjectVersion, session)

    def get_versions(
        self,
        project_id: str,
        limit: int = 50
    ) -> List[ProjectVersion]:
        """Get version history for a project."""
        return self.session.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).limit(limit).all()

    def get_latest_version(self, project_id: str) -> Optional[ProjectVersion]:
        """Get the latest version of a project."""
        return self.session.query(ProjectVersion).filter(
            ProjectVersion.project_id == project_id
        ).order_by(ProjectVersion.version_number.desc()).first()

    def create_version(
        self,
        project: Project,
        message: str = ""
    ) -> ProjectVersion:
        """Create a new version snapshot of a project."""
        latest = self.get_latest_version(project.id)
        next_version = (latest.version_number + 1) if latest else 1

        version = ProjectVersion(
            project_id=project.id,
            version_number=next_version,
            snapshot=project.to_legacy_dict(),
            message=message,
        )
        return self.create(version)


class AsyncProjectRepository(AsyncBaseRepository[Project]):
    """Async version of ProjectRepository for FastAPI."""

    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)

    async def get_by_workspace(
        self,
        workspace_id: str,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Project]:
        """Get all projects in a workspace."""
        stmt = select(Project).where(Project.workspace_id == workspace_id)

        if not include_deleted:
            stmt = stmt.where(Project.deleted_at.is_(None))

        stmt = stmt.order_by(Project.updated_at.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_with_elements(self, id: str) -> Optional[Project]:
        """Get project with all building elements loaded."""
        stmt = select(Project).options(
            joinedload(Project.walls),
            joinedload(Project.doors),
            joinedload(Project.windows),
            joinedload(Project.rooms),
            joinedload(Project.wall_types),
            joinedload(Project.roofs),
            joinedload(Project.sheets),
        ).where(Project.id == id)

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def search(
        self,
        workspace_id: str,
        query: str,
        limit: int = 20
    ) -> List[Project]:
        """Search projects by name."""
        stmt = select(Project).where(
            and_(
                Project.workspace_id == workspace_id,
                Project.deleted_at.is_(None),
                Project.name.ilike(f"%{query}%")
            )
        ).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
