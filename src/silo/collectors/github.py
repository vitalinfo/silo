"""GitHub collector (GraphQL).

For each person × org × period we run up to 3 paginated GraphQL searches:
  - is:pr author:LOGIN org:ORG created:FROM..TO              (authored, with PR-level fields)
  - is:pr reviewed-by:LOGIN -author:LOGIN org:ORG updated:.. (PRs reviewed + their reviews)
  - is:pr commenter:LOGIN -author:LOGIN org:ORG updated:..   (PRs commented + their comments)

Each query pulls up to 100 PRs per page with nested reviews/comments in a single
round-trip, so 170 reviewed PRs in a month resolves in 2-4 queries instead of
~340 sequential REST calls. Results are cached per (source, gh_login, from, to).

Inaccessible orgs return 0 search results in GraphQL (not an error). If we get
an explicit GraphQL error for a query (e.g. SAML), we log and skip that org.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone

from ..cache import Cache
from ..types import IssueComment, PullRequest, Review
from ._graphql import (
    QUERY_PRS_AUTHORED,
    QUERY_PRS_WITH_COMMENTS,
    QUERY_PRS_WITH_REVIEWS,
    GraphQLClient,
    GraphQLError,
)

log = logging.getLogger(__name__)

VALID_REVIEW_STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED"}
PAGE_SIZE_PRS = 100      # PRs-only query is light
PAGE_SIZE_NESTED = 50    # PRs + reviews/comments — keep nested cost reasonable


class GitHubCollector:
    SOURCE_PRS = "gh:prs_authored"
    SOURCE_REVIEWS = "gh:reviews_given"
    SOURCE_COMMENTS = "gh:comments_left"

    def __init__(self, token: str, orgs: list[str], cache: Cache) -> None:
        self._gql = GraphQLClient(token)
        self._orgs = orgs
        self._cache = cache

    # --- public API ----------------------------------------------------

    def prs_authored(self, gh_login: str, frm: date, to: date) -> list[PullRequest]:
        cached = self._cache.get(self.SOURCE_PRS, gh_login, frm, to)
        if cached is not None:
            log.info("[cache] prs_authored %s %s..%s = %d", gh_login, frm, to, len(cached))
            return [PullRequest.model_validate(r) for r in cached]

        results: list[PullRequest] = []
        for org in self._orgs:
            q = f"is:pr author:{gh_login} org:{org} created:{frm.isoformat()}..{to.isoformat()}"
            log.info("[gh] %s", q)
            for node in self._search(QUERY_PRS_AUTHORED, q, PAGE_SIZE_PRS):
                author = (node.get("author") or {}).get("login") or "ghost"
                results.append(
                    PullRequest(
                        org=node["repository"]["owner"]["login"],
                        repo=node["repository"]["name"],
                        number=node["number"],
                        author=author,
                        created_at=_parse_iso(node["createdAt"]),
                        merged_at=_parse_iso(node.get("mergedAt")),
                        closed_at=_parse_iso(node.get("closedAt")),
                        additions=node.get("additions", 0),
                        deletions=node.get("deletions", 0),
                    )
                )
        self._cache.put(
            self.SOURCE_PRS, gh_login, frm, to,
            [r.model_dump(mode="json") for r in results],
        )
        return results

    def reviews_given(self, gh_login: str, frm: date, to: date) -> list[Review]:
        cached = self._cache.get(self.SOURCE_REVIEWS, gh_login, frm, to)
        if cached is not None:
            log.info("[cache] reviews_given %s %s..%s = %d", gh_login, frm, to, len(cached))
            return [Review.model_validate(r) for r in cached]

        results: list[Review] = []
        frm_dt = datetime.combine(frm, time.min, tzinfo=timezone.utc)
        to_dt = datetime.combine(to, time.max, tzinfo=timezone.utc)

        for org in self._orgs:
            q = (
                f"is:pr reviewed-by:{gh_login} -author:{gh_login} "
                f"org:{org} updated:{frm.isoformat()}..{to.isoformat()}"
            )
            log.info("[gh] %s", q)
            for node in self._search(QUERY_PRS_WITH_REVIEWS, q, PAGE_SIZE_NESTED):
                reviews_conn = node.get("reviews") or {}
                if reviews_conn.get("totalCount", 0) > 100:
                    log.warning(
                        "PR %s/%s#%s has >100 reviews; only first 100 fetched",
                        node["repository"]["owner"]["login"],
                        node["repository"]["name"],
                        node["number"],
                    )
                for r in reviews_conn.get("nodes") or []:
                    reviewer = (r.get("author") or {}).get("login")
                    if reviewer != gh_login:
                        continue
                    state = r.get("state")
                    if state not in VALID_REVIEW_STATES:
                        continue  # PENDING or unknown
                    submitted = _parse_iso(r.get("submittedAt"))
                    if submitted is None or not (frm_dt <= submitted <= to_dt):
                        continue
                    pr_author = (node.get("author") or {}).get("login") or "ghost"
                    results.append(
                        Review(
                            pr_org=node["repository"]["owner"]["login"],
                            pr_repo=node["repository"]["name"],
                            pr_number=node["number"],
                            pr_author=pr_author,
                            reviewer=gh_login,
                            state=state,  # type: ignore[arg-type]
                            submitted_at=submitted,
                            body_chars=len(r.get("bodyText") or ""),
                        )
                    )
        self._cache.put(
            self.SOURCE_REVIEWS, gh_login, frm, to,
            [r.model_dump(mode="json") for r in results],
        )
        return results

    def comments_left(self, gh_login: str, frm: date, to: date) -> list[IssueComment]:
        cached = self._cache.get(self.SOURCE_COMMENTS, gh_login, frm, to)
        if cached is not None:
            log.info("[cache] comments_left %s %s..%s = %d", gh_login, frm, to, len(cached))
            return [IssueComment.model_validate(r) for r in cached]

        results: list[IssueComment] = []
        frm_dt = datetime.combine(frm, time.min, tzinfo=timezone.utc)
        to_dt = datetime.combine(to, time.max, tzinfo=timezone.utc)

        for org in self._orgs:
            q = (
                f"is:pr commenter:{gh_login} -author:{gh_login} "
                f"org:{org} updated:{frm.isoformat()}..{to.isoformat()}"
            )
            log.info("[gh] %s", q)
            for node in self._search(QUERY_PRS_WITH_COMMENTS, q, PAGE_SIZE_NESTED):
                comments_conn = node.get("comments") or {}
                if comments_conn.get("totalCount", 0) > 100:
                    log.warning(
                        "PR %s/%s#%s has >100 comments; only first 100 fetched",
                        node["repository"]["owner"]["login"],
                        node["repository"]["name"],
                        node["number"],
                    )
                for c in comments_conn.get("nodes") or []:
                    commenter = (c.get("author") or {}).get("login")
                    if commenter != gh_login:
                        continue
                    created = _parse_iso(c.get("createdAt"))
                    if created is None or not (frm_dt <= created <= to_dt):
                        continue
                    pr_author = (node.get("author") or {}).get("login") or "ghost"
                    results.append(
                        IssueComment(
                            pr_org=node["repository"]["owner"]["login"],
                            pr_repo=node["repository"]["name"],
                            pr_number=node["number"],
                            pr_author=pr_author,
                            author=gh_login,
                            created_at=created,
                            body_chars=len(c.get("bodyText") or ""),
                        )
                    )
        self._cache.put(
            self.SOURCE_COMMENTS, gh_login, frm, to,
            [r.model_dump(mode="json") for r in results],
        )
        return results

    def close(self) -> None:
        self._gql.close()

    # --- internal ------------------------------------------------------

    def _search(self, query: str, q: str, page_size: int):
        try:
            yield from self._gql.paginated_search(query, q, page_size=page_size)
        except GraphQLError as e:
            log.warning("Skipping query — GraphQL error: q=%s errors=%s", q, e.errors)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))
