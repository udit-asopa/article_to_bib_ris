from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import UrlCheckResult
from .utils import is_doi_url

DOI_ACCESS_RESTRICTED_HTTP_CODES = {401, 403, 406, 429}
REFHUB_ACCESS_RESTRICTED_HTTP_CODES = {403}
REFHUB_HOSTS = {"refhub.elsevier.com"}


def is_well_formed_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "unsupported scheme"
    if not parsed.netloc:
        return False, "missing domain"
    return True, "format ok"


def _is_access_restricted_doi(url: str, http_code: int) -> bool:
    return is_doi_url(url) and http_code in DOI_ACCESS_RESTRICTED_HTTP_CODES


def _is_access_restricted_refhub(url: str, http_code: int) -> bool:
    host = urlparse(url).netloc.lower()
    return host in REFHUB_HOSTS and http_code in REFHUB_ACCESS_RESTRICTED_HTTP_CODES


def _handle_http_error(url: str, error: HTTPError) -> tuple[bool, str] | None:
    if error.code in {405, 501}:
        return None
    if _is_access_restricted_doi(url, error.code):
        return True, f"likely valid DOI (http {error.code}, access restricted)"
    if _is_access_restricted_refhub(url, error.code):
        return True, f"likely valid link (http {error.code}, access restricted)"
    return False, f"http {error.code}"


def _request_url(
    url: str, timeout_seconds: float, method: str
) -> tuple[bool, str, tuple[str, ...]] | None:
    headers = {"User-Agent": "Mozilla/5.0 (URL-Checker)"}

    try:
        request = Request(url, headers=headers, method=method)
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None)
            final_url = response.geturl() if hasattr(response, "geturl") else None
            redirects = (final_url,) if final_url and final_url != url else ()
            if status is None or status < 400:
                return (
                    True,
                    f"reachable ({status})" if status is not None else "reachable",
                    redirects,
                )
            return False, f"http {status}", redirects
    except HTTPError as error:
        result = _handle_http_error(url, error)
        if result is None:
            return None
        return result[0], result[1], ()
    except URLError as error:
        return False, f"network error: {error.reason}", ()
    except Exception as error:
        return False, f"error: {error}", ()


def check_url_reachable(
    url: str, timeout_seconds: float
) -> tuple[bool, str, tuple[str, ...]]:
    head_result = _request_url(url=url, timeout_seconds=timeout_seconds, method="HEAD")
    if head_result is not None:
        return head_result

    get_result = _request_url(url=url, timeout_seconds=timeout_seconds, method="GET")
    if get_result is not None:
        return get_result

    return False, "request failed", ()


def validate_single_url(url: str, timeout_seconds: float) -> UrlCheckResult:
    is_well_formed, format_reason = is_well_formed_url(url)
    if not is_well_formed:
        return UrlCheckResult(url=url, is_valid=False, reason=format_reason)

    is_reachable, reason, redirected_links = check_url_reachable(
        url=url, timeout_seconds=timeout_seconds
    )
    return UrlCheckResult(
        url=url, is_valid=is_reachable, reason=reason, redirected_links=redirected_links
    )


def validate_urls(
    urls: list[str], timeout_seconds: float, workers: int
) -> list[UrlCheckResult]:
    if not urls:
        return []

    max_workers = max(1, min(workers, len(urls)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(
            executor.map(
                lambda current_url: validate_single_url(current_url, timeout_seconds),
                urls,
            )
        )
