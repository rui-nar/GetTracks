"""ProjectManager — owns the single open project and tracks dirty state."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from src.models.project import Project
from src.project.project_io import ProjectIO


class ProjectManager(QObject):
    """Qt object that holds the currently open :class:`Project`.

    Signals
    -------
    project_changed(Project | None)
        Emitted when a project is opened, created, or closed.
    dirty_changed(bool)
        Emitted when the unsaved-changes flag toggles.
    save_path_changed(str)
        Emitted when the file path is set or changed (Save As).
    """

    project_changed = pyqtSignal(object)   # Project or None
    dirty_changed   = pyqtSignal(bool)
    save_path_changed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._project: Optional[Project] = None
        self._path: Optional[str] = None
        self._dirty: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def project(self) -> Optional[Project]:
        return self._project

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def has_project(self) -> bool:
        return self._project is not None

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def new_project(self, name: str) -> Project:
        """Create a fresh empty project and make it the current one."""
        self._project = Project(name=name)
        self._path = None
        self._set_dirty(False)
        self.project_changed.emit(self._project)
        return self._project

    def open_project(self, path: str) -> Project:
        """Load a project from *path* and make it the current one."""
        self._project = ProjectIO.load(path)
        self._path = path
        self._set_dirty(False)
        self.project_changed.emit(self._project)
        return self._project

    def close_project(self) -> None:
        """Discard the current project (caller is responsible for save prompt)."""
        self._project = None
        self._path = None
        self._set_dirty(False)
        self.project_changed.emit(None)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> bool:
        """Save to the current path.  Returns False if no path is set."""
        if self._path and self._project:
            ProjectIO.save(self._project, self._path)
            self._set_dirty(False)
            return True
        return False

    def save_as(self, path: str) -> None:
        """Save to *path* and update the current path."""
        if self._project is None:
            return
        ProjectIO.save(self._project, path)
        self._path = path
        self._set_dirty(False)
        self.save_path_changed.emit(path)

    # ------------------------------------------------------------------
    # Dirty flag
    # ------------------------------------------------------------------

    def mark_dirty(self) -> None:
        """Signal that the project has unsaved changes."""
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirty_changed.emit(dirty)
