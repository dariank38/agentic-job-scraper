"""Site-specific parsers for website content."""

from web_crawler.parsers.v2ex import parse_v2ex_post
from web_crawler.parsers.eleduck import parse_eleduck_post

__all__ = ["parse_v2ex_post", "parse_eleduck_post"]
