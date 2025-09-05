import logging
from typing import Optional

import httpx


class YouTrackError(RuntimeError):
    pass


class YouTrackClient:
    def __init__(self, base_url: str, token: str):
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        self.base_url = base_url
        self._log = logging.getLogger("tulipee.youtrack")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    async def create_issue(
        self,
        summary: str,
        description: Optional[str] = None,
        *,
        project_id: str,
        type_name: Optional[str] = None,
        fields: str = "id,idReadable,summary,description,created,updated,project(id,name,shortName)",
    ) -> dict:
        """Create a YouTrack issue in the given project.

        This uses the YouTrack REST API: POST /api/issues
        Body minimally includes summary, project, and optional description.
        """
        payload: dict = {
            "summary": summary,
            "project": {"id": project_id},
        }
        if description:
            payload["description"] = description
        # Optional: set Type custom field (e.g., Task/Bug)
        if type_name:
            payload["customFields"] = [
                {
                    "name": "Type",
                    "value": {"name": type_name},
                }
            ]

        self._log.debug("Creating YouTrack issue in project_id=%s", project_id)
        resp = await self.client.post(
            "/api/issues",
            params={"fields": fields},
            json=payload,
        )
        if resp.status_code not in (200, 201):
            self._log.error("YouTrack create failed %s %s", resp.status_code, resp.text)
            raise YouTrackError(f"[{resp.status_code}] {resp.text}")
        data = resp.json()
        self._log.info(
            "Created YouTrack issue %s (%s)", data.get("idReadable"), data.get("id")
        )
        return data
