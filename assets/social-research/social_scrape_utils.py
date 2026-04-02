#!/usr/bin/env python3
"""
Social media scraping utilities for the marketing pipeline.
Zero pip dependencies — uses only Python standard library.

Provides authenticated and public scraping for Reddit, Twitter/X, and Telegram.
The social-researcher agent copies this module into its working directory and imports it.

Usage:
    from social_scrape_utils import RedditScraper, TwitterScraper, TelegramScraper
"""

import json
import time
import hashlib
import hmac
import base64
import urllib.request
import urllib.parse
import urllib.error
import os
import re
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DELAY_BETWEEN_REQUESTS = 2.0   # seconds — respect platform rate limits
REQUEST_TIMEOUT = 30           # seconds per HTTP request
MAX_RETRIES = 3
USER_AGENT = "MarketingPipeline/1.0 SocialResearch (compatible; +https://github.com)"

# ---------------------------------------------------------------------------
# HTTP utilities
# ---------------------------------------------------------------------------

def fetch(url, headers=None, data=None, method=None, timeout=REQUEST_TIMEOUT):
    """Make an HTTP request using urllib. Returns dict with status, headers, body."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)

    if isinstance(data, str):
        data = data.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)

    # Accept self-signed certs for local dev (some nitter instances)
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"status": e.code, "body": body, "headers": {}}
    except Exception as e:
        return {"status": 0, "body": str(e), "headers": {}}


def fetch_with_retry(url, headers=None, data=None, method=None,
                     max_retries=MAX_RETRIES, base_delay=2.0):
    """Fetch with exponential backoff on failure / 429 / 5xx."""
    last_resp = None
    for attempt in range(max_retries + 1):
        resp = fetch(url, headers=headers, data=data, method=method)
        last_resp = resp

        if resp["status"] == 200:
            return resp

        if resp["status"] in (429, 500, 502, 503) and attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            time.sleep(delay)
            continue

        # Non-retryable error or last attempt
        break

    return last_resp


def fetch_json(url, headers=None, data=None, method=None):
    """Fetch URL and parse response as JSON."""
    resp = fetch_with_retry(url, headers=headers, data=data, method=method)
    if resp["status"] != 200:
        return None, resp
    try:
        return json.loads(resp["body"]), resp
    except json.JSONDecodeError:
        return None, resp


def rate_limit_pause():
    """Sleep to respect rate limits between requests."""
    time.sleep(DELAY_BETWEEN_REQUESTS)


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

class RedditScraper:
    """Scrape Reddit via OAuth API or public JSON API."""

    def __init__(self, credentials=None):
        """
        credentials: dict with client_id, client_secret, username, password, user_agent
        If None, uses public JSON API (no auth, lower rate limits).
        """
        self.token = None
        self.creds = credentials
        self.user_agent = (credentials or {}).get("user_agent", USER_AGENT)

    def authenticate(self):
        """Get OAuth 2.0 access token via password grant."""
        if not self.creds:
            return False

        c = self.creds
        required = ["client_id", "client_secret", "username", "password"]
        if not all(c.get(k) for k in required):
            return False

        auth_str = base64.b64encode(
            f"{c['client_id']}:{c['client_secret']}".encode()
        ).decode()

        body = urllib.parse.urlencode({
            "grant_type": "password",
            "username": c["username"],
            "password": c["password"]
        })

        resp = fetch(
            "https://www.reddit.com/api/v1/access_token",
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": self.user_agent,
            },
            data=body,
            method="POST",
        )

        if resp["status"] == 200:
            data = json.loads(resp["body"])
            if data.get("access_token"):
                self.token = data["access_token"]
                return True
        return False

    def search(self, query, subreddit=None, sort="relevance", time_filter="month", limit=25):
        """Search Reddit for posts matching the query."""
        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": str(min(limit, 100)),
            "type": "link",
        }
        qs = urllib.parse.urlencode(params)

        if self.token:
            # Authenticated API
            base = f"https://oauth.reddit.com/r/{subreddit}/search" if subreddit else "https://oauth.reddit.com/search"
            if subreddit:
                params["restrict_sr"] = "true"
                qs = urllib.parse.urlencode(params)
            url = f"{base}?{qs}"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "User-Agent": self.user_agent,
            }
        else:
            # Public JSON API
            base = f"https://www.reddit.com/r/{subreddit}/search.json" if subreddit else "https://www.reddit.com/search.json"
            if subreddit:
                params["restrict_sr"] = "true"
                qs = urllib.parse.urlencode(params)
            url = f"{base}?{qs}"
            headers = {"User-Agent": self.user_agent}

        data, resp = fetch_json(url, headers=headers)
        rate_limit_pause()

        if not data:
            return []

        posts = []
        children = data.get("data", {}).get("children", [])
        for child in children:
            p = child.get("data", {})
            posts.append({
                "title": p.get("title", ""),
                "body": (p.get("selftext", "") or "")[:500],
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "subreddit": p.get("subreddit", ""),
                "author": p.get("author", ""),
                "created_utc": p.get("created_utc", 0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "flair": p.get("link_flair_text", ""),
            })

        return posts

    def get_comments(self, permalink, limit=5):
        """Get top comments for a post by permalink."""
        if permalink.startswith("https://"):
            permalink = permalink.replace("https://reddit.com", "").replace("https://www.reddit.com", "")

        if self.token:
            url = f"https://oauth.reddit.com{permalink}.json?sort=top&limit={limit}"
            headers = {"Authorization": f"Bearer {self.token}", "User-Agent": self.user_agent}
        else:
            url = f"https://www.reddit.com{permalink}.json?sort=top&limit={limit}"
            headers = {"User-Agent": self.user_agent}

        data, resp = fetch_json(url, headers=headers)
        rate_limit_pause()

        if not data or not isinstance(data, list) or len(data) < 2:
            return []

        comments = []
        children = data[1].get("data", {}).get("children", [])
        for child in children[:limit]:
            c = child.get("data", {})
            if child.get("kind") != "t1":
                continue
            comments.append({
                "body": (c.get("body", "") or "")[:300],
                "score": c.get("score", 0),
                "author": c.get("author", ""),
            })

        return comments

    def get_subreddit_hot(self, subreddit, limit=10):
        """Get hot posts from a subreddit."""
        if self.token:
            url = f"https://oauth.reddit.com/r/{subreddit}/hot?limit={limit}"
            headers = {"Authorization": f"Bearer {self.token}", "User-Agent": self.user_agent}
        else:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
            headers = {"User-Agent": self.user_agent}

        data, resp = fetch_json(url, headers=headers)
        rate_limit_pause()

        if not data:
            return []

        posts = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            posts.append({
                "title": p.get("title", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "subreddit": subreddit,
                "url": f"https://reddit.com{p.get('permalink', '')}",
            })

        return posts


# ---------------------------------------------------------------------------
# Twitter/X — OAuth 1.0a
# ---------------------------------------------------------------------------

class TwitterScraper:
    """Search Twitter/X via OAuth 1.0a API v2 or public fallback."""

    def __init__(self, credentials=None):
        """
        credentials: dict with api_key, api_secret, access_token, access_token_secret
        If None, falls back to WebSearch-style public scraping hints.
        """
        self.creds = credentials
        self.has_auth = bool(
            credentials
            and credentials.get("api_key")
            and credentials.get("api_secret")
            and credentials.get("access_token")
            and credentials.get("access_token_secret")
        )

    def _percent_encode(self, s):
        return urllib.parse.quote(str(s), safe="")

    def _generate_oauth_params(self):
        c = self.creds
        return {
            "oauth_consumer_key": c["api_key"],
            "oauth_nonce": hashlib.sha256(os.urandom(32)).hexdigest()[:32],
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": c["access_token"],
            "oauth_version": "1.0",
        }

    def _sign_request(self, method, url, params):
        c = self.creds
        param_string = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}"
            for k, v in sorted(params.items())
        )

        base_string = "&".join([
            method.upper(),
            self._percent_encode(url),
            self._percent_encode(param_string),
        ])

        signing_key = f"{self._percent_encode(c['api_secret'])}&{self._percent_encode(c['access_token_secret'])}"
        signature = hmac.new(
            signing_key.encode(), base_string.encode(), hashlib.sha1
        ).digest()
        return base64.b64encode(signature).decode()

    def _build_auth_header(self, oauth_params):
        parts = " ".join(
            f'{self._percent_encode(k)}="{self._percent_encode(v)}",'
            for k, v in sorted(oauth_params.items())
            if k.startswith("oauth_")
        ).rstrip(",")
        return f"OAuth {parts}"

    def _api_request(self, method, url, query_params=None):
        """Make an OAuth 1.0a signed request to Twitter API."""
        oauth_params = self._generate_oauth_params()

        # Build signature from OAuth params + query params
        sig_params = dict(oauth_params)
        if query_params:
            sig_params.update(query_params)

        signature = self._sign_request(method, url, sig_params)
        oauth_params["oauth_signature"] = signature

        # Add query string to URL
        full_url = url
        if query_params:
            full_url += "?" + urllib.parse.urlencode(query_params)

        headers = {
            "Authorization": self._build_auth_header(oauth_params),
            "User-Agent": USER_AGENT,
        }

        return fetch_with_retry(full_url, headers=headers, method=method)

    def search_recent(self, query, max_results=50):
        """Search recent tweets (last 7 days) via Twitter API v2."""
        if not self.has_auth:
            return []

        params = {
            "query": query,
            "max_results": str(min(max_results, 100)),
            "tweet.fields": "public_metrics,created_at,author_id,conversation_id",
        }

        resp = self._api_request("GET", "https://api.twitter.com/2/tweets/search/recent", params)
        rate_limit_pause()

        if resp["status"] != 200:
            return []

        try:
            data = json.loads(resp["body"])
        except json.JSONDecodeError:
            return []

        tweets = []
        for t in data.get("data", []):
            metrics = t.get("public_metrics", {})
            tweets.append({
                "text": t.get("text", ""),
                "created_at": t.get("created_at", ""),
                "author_id": t.get("author_id", ""),
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "conversation_id": t.get("conversation_id", ""),
            })

        return tweets

    def public_search_hints(self, query):
        """Return search URLs for manual/WebSearch-based Twitter research (no auth)."""
        encoded = urllib.parse.quote(query)
        return {
            "twitter_search_url": f"https://twitter.com/search?q={encoded}&src=typed_query&f=top",
            "x_search_url": f"https://x.com/search?q={encoded}&src=typed_query&f=top",
            "websearch_query": f"site:twitter.com OR site:x.com {query}",
            "note": "Use WebSearch with the websearch_query to find relevant tweets, then WebFetch individual tweet URLs.",
        }


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

class _TelegramHTMLParser(HTMLParser):
    """Parse Telegram public channel HTML (t.me/s/channel) for messages."""

    def __init__(self):
        super().__init__()
        self.messages = []
        self._in_message = False
        self._in_text = False
        self._in_date = False
        self._in_views = False
        self._current = {}
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        if "tgme_widget_message_wrap" in cls or "tgme_widget_message " in cls:
            self._in_message = True
            self._current = {"text": "", "date": "", "views": "", "channel": ""}

        if self._in_message:
            if "tgme_widget_message_text" in cls:
                self._in_text = True
                self._current_text = []
            if "tgme_widget_message_date" in cls:
                self._in_date = True
                if "datetime" in attrs_dict:
                    self._current["date"] = attrs_dict.get("datetime", "")
            if tag == "time" and "datetime" in attrs_dict:
                self._current["date"] = attrs_dict["datetime"]
            if "tgme_widget_message_views" in cls:
                self._in_views = True

    def handle_endtag(self, tag):
        if self._in_text and tag in ("div", "span"):
            self._in_text = False
            self._current["text"] = " ".join(self._current_text).strip()
        if self._in_date:
            self._in_date = False
        if self._in_views:
            self._in_views = False

        if self._in_message and tag == "div":
            if self._current.get("text"):
                self.messages.append(dict(self._current))
            self._in_message = False

    def handle_data(self, data):
        if self._in_text:
            self._current_text.append(data.strip())
        if self._in_views:
            self._current["views"] = data.strip()


class TelegramScraper:
    """Scrape public Telegram channels via their web preview."""

    def __init__(self, credentials=None):
        """credentials: dict with bot_token, chat_id (currently unused for scraping)."""
        self.creds = credentials

    def scrape_public_channel(self, channel_name, limit=30):
        """
        Scrape messages from a public Telegram channel via t.me/s/{channel}.
        Returns list of dicts with text, date, views, channel.
        """
        # Remove @ prefix if present
        channel_name = channel_name.lstrip("@")
        url = f"https://t.me/s/{channel_name}"

        resp = fetch_with_retry(url)
        rate_limit_pause()

        if resp["status"] != 200:
            return []

        parser = _TelegramHTMLParser()
        try:
            parser.feed(resp["body"])
        except Exception:
            return []

        messages = parser.messages[-limit:]
        for m in messages:
            m["channel"] = channel_name

        return messages

    def search_channels(self, query):
        """Return search hints for finding relevant Telegram channels."""
        encoded = urllib.parse.quote(query)
        return {
            "tgstat_url": f"https://tgstat.com/en/search?q={encoded}",
            "websearch_query": f"telegram channel {query}",
            "note": "Use WebSearch with the websearch_query to discover public Telegram channels, then use scrape_public_channel() on each.",
        }


# ---------------------------------------------------------------------------
# Credential loader
# ---------------------------------------------------------------------------

def load_credentials(path=None):
    """
    Load distribution credentials from ~/.marketing-pipeline/distribution.json.
    Returns dict with platform configs, or empty dict if file doesn't exist.
    """
    if path is None:
        path = os.path.expanduser("~/.marketing-pipeline/distribution.json")

    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# Main (for standalone testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 social_scrape_utils.py <test_query>")
        print("Tests Reddit public search with the given query.")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    print(f"Testing Reddit public search for: {query}\n")

    reddit = RedditScraper()
    posts = reddit.search(query, limit=5)
    print(f"Found {len(posts)} posts:")
    for p in posts:
        print(f"  [{p['score']:>5}] r/{p['subreddit']}: {p['title'][:80]}")

    print(f"\nTesting Twitter public search hints:")
    twitter = TwitterScraper()
    hints = twitter.public_search_hints(query)
    for k, v in hints.items():
        print(f"  {k}: {v}")

    print(f"\nTesting Telegram channel search hints:")
    telegram = TelegramScraper()
    hints = telegram.search_channels(query)
    for k, v in hints.items():
        print(f"  {k}: {v}")
