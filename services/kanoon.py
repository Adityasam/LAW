# services/kanoon.py
# ---------------------------------------------------------------------------
# Thin wrapper around the Indian Kanoon REST API.
# Used by routes/chat.py to fetch judgments and full-text documents.
# Indian Kanoon uses HTTP Basic Auth — supply (api_key, "") as the tuple.
# ---------------------------------------------------------------------------
import json
from typing import Any, Dict, List, Optional, Union

import requests
from requests.exceptions import RequestException


class IndianKanoonError(Exception):
    """Raised when the Indian Kanoon API returns an error or is unreachable."""


class IndianKanoon:
    """
    Minimal client for the public Indian Kanoon search & document endpoints.

    Usage:
        kanoon = IndianKanoon(api_key="<your-key>")
        results = kanoon.search("Section 103 BNS bail")
        doc     = kanoon.fetch_doc(123456)
    """

    BASE_URL = "https://api.indiankanoon.org"
    TIMEOUT = 15  # seconds

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or ""
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        # Indian Kanoon uses HTTP Basic auth with the API key as the username.
        self._auth = (self.api_key, "") if self.api_key else None

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": f"VakilAI/0.1 (+kanoon-client)",
        }

    def _parse(self, resp: requests.Response) -> Dict[str, Any]:
        """Decode JSON if possible, otherwise return a structured error body."""
        try:
            return resp.json()
        except ValueError:
            return {
                "ok": False,
                "status": resp.status_code,
                "text": resp.text[:2000],
            }

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(
                method,
                url,
                headers=self._headers(),
                auth=self._auth,
                timeout=self.TIMEOUT,
                **kwargs,
            )
        except RequestException as exc:
            raise IndianKanoonError(f"Network error contacting Indian Kanoon: {exc}") from exc

        if resp.status_code >= 400:
            raise IndianKanoonError(
                f"Indian Kanoon API error {resp.status_code} for {path}: {resp.text[:300]}"
            )

        return self._parse(resp)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def search(self, query: str, pagenum: int = 0) -> Dict[str, Any]:
        """
        Search Indian Kanoon for judgments matching `query`.

        Returns the parsed JSON envelope from the API. Typical keys include
        `docs` (list of result summaries), `found`, and `pages`.
        """
        if not query or not query.strip():
            raise ValueError("search() requires a non-empty query string")

        params = {"formInput": query, "pagenum": pagenum}
        return self._request("GET", "/search/", params=params)

    def fetch_doc(self, docid: Union[int, str]) -> Dict[str, Any]:
        """
        Fetch the full record for a single Indian Kanoon document by its id.
        Returns the parsed JSON envelope; typically contains `title`, `doc`,
        `citeList`, etc.
        """
        if not docid:
            raise ValueError("fetch_doc() requires a docid")

        return self._request("GET", f"/doc/{docid}/")
