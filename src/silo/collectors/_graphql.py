"""Tiny GraphQL client for the GitHub API.

GH search via REST forces a per-PR fetch for reviews/comments, which is
O(N) sequential round-trips. GraphQL lets us pull a PR + its reviews + its
comments in a single nested query, with up to 100 PRs per page. For our
volumes (~hundreds of PRs/person/period), this is ~10-100x faster than REST.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

import httpx

log = logging.getLogger(__name__)

GH_GRAPHQL_URL = "https://api.github.com/graphql"


class GraphQLError(RuntimeError):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__(errors)
        self.errors = errors


class GraphQLClient:
    def __init__(self, token: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )

    def query(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(GH_GRAPHQL_URL, json={"query": query, "variables": variables})
        resp.raise_for_status()
        body = resp.json()
        if "errors" in body and body["errors"]:
            raise GraphQLError(body["errors"])
        return body["data"]

    def paginated_search(
        self,
        query: str,
        q: str,
        page_size: int = 50,
    ) -> Iterator[dict[str, Any]]:
        """Yield PullRequest nodes across all pages of a search query."""
        cursor: str | None = None
        page = 0
        while True:
            variables: dict[str, Any] = {"q": q, "first": page_size, "after": cursor}
            data = self.query(query, variables)
            search = data["search"]
            page += 1
            nodes = search.get("nodes") or []
            for node in nodes:
                if node:  # null for non-PullRequest types in mixed search
                    yield node
            page_info = search.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                if page == 1 and search.get("issueCount", 0) >= 1000:
                    log.warning(
                        "GraphQL search hit 1000-result hard cap; results truncated. q=%s", q
                    )
                break
            cursor = page_info["endCursor"]

    def close(self) -> None:
        self._client.close()


# --- Query strings -------------------------------------------------------

QUERY_PRS_AUTHORED = """
query($q: String!, $first: Int!, $after: String) {
  search(query: $q, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo { endCursor hasNextPage }
    nodes {
      ... on PullRequest {
        number
        createdAt
        mergedAt
        closedAt
        additions
        deletions
        author { login }
        repository { name owner { login } }
      }
    }
  }
}
"""

QUERY_PRS_WITH_REVIEWS = """
query($q: String!, $first: Int!, $after: String) {
  search(query: $q, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo { endCursor hasNextPage }
    nodes {
      ... on PullRequest {
        number
        author { login }
        repository { name owner { login } }
        reviews(first: 100) {
          totalCount
          nodes {
            author { login }
            state
            submittedAt
            bodyText
          }
        }
      }
    }
  }
}
"""

QUERY_PRS_WITH_COMMENTS = """
query($q: String!, $first: Int!, $after: String) {
  search(query: $q, type: ISSUE, first: $first, after: $after) {
    issueCount
    pageInfo { endCursor hasNextPage }
    nodes {
      ... on PullRequest {
        number
        author { login }
        repository { name owner { login } }
        comments(first: 100) {
          totalCount
          nodes {
            author { login }
            createdAt
            bodyText
          }
        }
      }
    }
  }
}
"""
