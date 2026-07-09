"""Сбор данных с Instagram, TikTok и YouTube через Apify для заданного диапазона дат."""
import os
import re
from datetime import date

from apify_client import ApifyClient

APIFY_TOKEN = os.environ["APIFY_TOKEN"]
client = ApifyClient(APIFY_TOKEN)

IG_ACTOR = "apify/instagram-post-scraper"
TT_ACTOR = "clockworks/tiktok-profile-scraper"
YT_ACTOR = "grow_media/youtube-channel-video-scraper"

PLATFORM_NAMES = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "youtube": "YouTube",
}


def detect_platform(url: str):
    u = url.lower()
    if "instagram.com" in u:
        return "instagram"
    if "tiktok.com" in u:
        return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return None


def _extract_ig_username(url: str) -> str:
    m = re.search(r"instagram\.com/([^/?#]+)", url)
    return m.group(1) if m else url


def _extract_tt_username(url: str) -> str:
    m = re.search(r"tiktok\.com/@([^/?#]+)", url)
    return m.group(1) if m else url.lstrip("@")


def _extract_yt_handle(url: str) -> str:
    m = re.search(r"youtube\.com/(@[^/?#]+)", url)
    return m.group(1) if m else url


def _within(d: date, start: date, end: date) -> bool:
    return start <= d <= end


def fetch_instagram(url: str, start: date, end: date, max_limit: int = 200):
    username = _extract_ig_username(url)
    limit = 40
    items = []
    while True:
        run = client.actor(IG_ACTOR).call(run_input={
            "username": [username],
            "resultsLimit": limit,
            "skipPinnedPosts": False,
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            break
        oldest_date = min(date.fromisoformat(it["timestamp"][:10]) for it in items)
        if oldest_date <= start or limit >= max_limit:
            break
        limit = min(limit * 2, max_limit)

    posts = []
    for it in items:
        d = date.fromisoformat(it["timestamp"][:10])
        if not _within(d, start, end):
            continue
        views = it.get("videoPlayCount") or it.get("videoViewCount") or 0
        posts.append({
            "date": d.isoformat(),
            "views": views,
            "likes": it.get("likesCount", 0),
            "comments": it.get("commentsCount", 0),
            "url": it.get("url") or "https://www.instagram.com/p/%s/" % it.get("shortCode", ""),
        })
    return posts


def fetch_tiktok(url: str, start: date, end: date, max_limit: int = 200):
    username = _extract_tt_username(url)
    limit = 40
    items = []
    while True:
        run = client.actor(TT_ACTOR).call(run_input={
            "profiles": [username],
            "resultsPerPage": limit,
            "profileSorting": "latest",
            "excludePinnedPosts": False,
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            break
        oldest_date = min(date.fromisoformat(it["createTimeISO"][:10]) for it in items)
        if oldest_date <= start or limit >= max_limit:
            break
        limit = min(limit * 2, max_limit)

    posts = []
    for it in items:
        d = date.fromisoformat(it["createTimeISO"][:10])
        if not _within(d, start, end):
            continue
        posts.append({
            "date": d.isoformat(),
            "views": it.get("playCount", 0),
            "likes": it.get("diggCount", 0),
            "comments": it.get("commentCount", 0),
            "shares": it.get("shareCount", 0),
            "url": it.get("webVideoUrl", ""),
        })
    return posts


def fetch_youtube(url: str, start: date, end: date, max_results: int = 300):
    handle = _extract_yt_handle(url)
    posts = []
    for video_type in ("short", "long"):
        run = client.actor(YT_ACTOR).call(run_input={
            "channelHandle": handle,
            "maxResults": max_results,
            "videoType": video_type,
            "sortOrder": "latest",
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        for it in items:
            d_str = (it.get("date") or "")[:10]
            if not d_str:
                continue
            d = date.fromisoformat(d_str)
            if not _within(d, start, end):
                continue
            posts.append({
                "date": d.isoformat(),
                "views": it.get("viewCount", 0),
                "likes": it.get("likes", 0),
                "comments": it.get("commentsCount", 0),
                "url": it.get("url", ""),
            })
    return posts


FETCHERS = {
    "instagram": fetch_instagram,
    "tiktok": fetch_tiktok,
    "youtube": fetch_youtube,
}
