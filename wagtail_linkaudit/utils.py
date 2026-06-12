from urllib.parse import urlparse, urlunparse


def is_valid_link(url):
    if not url:
        return False

    url = url.strip().lower()

    # Check for invalid protocols and patterns
    return not (
        url.startswith("mailto:")
        or url.startswith("tel:")
        or url.startswith("javascript:")
        or url.startswith("#")
        or url.endswith("#")  # Catches URLs that are just fragments after urljoin
    )


def normalize_url(url):
    parsed = urlparse(url)

    parsed = parsed._replace(fragment="")
    parsed = parsed._replace(query="")

    path = parsed.path.rstrip("/")
    parsed = parsed._replace(path=path)

    return urlunparse(parsed)


def is_internal(base_url, test_url):
    return urlparse(base_url).netloc == urlparse(test_url).netloc


SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif",
    ".zip", ".mp4", ".mp3"
)


def should_skip(url):
    return url.lower().endswith(SKIP_EXTENSIONS)