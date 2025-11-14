from urllib.parse import urlparse


def is_https(url):
    try:
        parsed_url = urlparse(url)
        return parsed_url.scheme == "https"
    except Exception:
        return False


def extract_domain_from_url(url):
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc + parsed_url.path
    except Exception:
        return url