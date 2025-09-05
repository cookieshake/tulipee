from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ProjectSpec:
    id: str          # YouTrack internal project id (e.g., "0-0")
    key: str         # Short key shown in issue IDs (e.g., "APP")
    name: str        # Human-readable name
    description: str # Guidance for when to use this project


# Fill this list with your real projects and guidance.
# Example:
# PROJECTS: List[ProjectSpec] = [
#     ProjectSpec(
#         id="0-0",
#         key="APP",
#         name="Mobile App",
#         description="모바일 앱(Android/iOS) 관련 사용자-facing 버그 및 기능 요청",
#     ),
#     ProjectSpec(
#         id="0-1",
#         key="BE",
#         name="Backend",
#         description="API, 인증, 데이터 파이프라인 등 서버 사이드 문제",
#     ),
# ]
PROJECTS: List[ProjectSpec] = [
    ProjectSpec(
        id="0-4",
        key="NRIY",
        name="나란잉여",
        description="나란잉여 봇을 만들기 위한 프로젝트입니다.",
    ),
]


def get_project_catalog() -> List[ProjectSpec]:
    """Return the project catalog to guide LLM selection.

    Edit `PROJECTS` above to add/update entries.
    """
    return PROJECTS


def resolve_project_id(
    *,
    project_id: Optional[str] = None,
    project_key: Optional[str] = None,
    project_name: Optional[str] = None,
) -> Optional[str]:
    """Resolve the YouTrack internal project id from id/key/name.

    - If `project_id` is given, return it.
    - Else match by key (case-insensitive), then by name (case-insensitive).
    - Returns None if no match.
    """
    if project_id:
        return project_id
    catalog = get_project_catalog()
    if project_key:
        key_l = project_key.strip().lower()
        for p in catalog:
            if p.key.lower() == key_l:
                return p.id
    if project_name:
        name_l = project_name.strip().lower()
        for p in catalog:
            if p.name.lower() == name_l:
                return p.id
    return None

