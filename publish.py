#!/usr/bin/env python3
# Publicador automatico Instagram @5asecentorno — roda via GitHub Actions.
import os, json, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone, timedelta

TOKEN = os.environ["IG_TOKEN"]
IG_USER = "17841459288001646"
BASE = "https://cdn.jsdelivr.net/gh/guilhermemarquesia/5asec-midia-julho@main"
GRAPH = "https://graph.facebook.com/v19.0"
DRY = os.environ.get("DRY_RUN", "false").lower() == "true"

SP = timezone(timedelta(hours=-3))  # America/Sao_Paulo (sem horario de verao)
now = datetime.now(SP)
DATE = os.environ.get("FORCE_DATE") or f"{now.day:02d}/{now.month:02d}"
hour = int(os.environ.get("FORCE_HOUR", now.hour))
SLOT = os.environ.get("FORCE_SLOT") or ("story" if hour < 11 else ("feed" if hour < 16 else "reels"))

schedule = json.load(open("cronograma.json", encoding="utf-8"))
due = [p for p in schedule if p["date"] == DATE and p["slot"] == SLOT]
print(f"[{now:%Y-%m-%d %H:%M} SP] data={DATE} slot={SLOT} dry={DRY} -> {len(due)} post(s)")

def api(path, params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{GRAPH}/{path}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: {e.read().decode()[:300]}")

def status(cid):
    with urllib.request.urlopen(f"{GRAPH}/{cid}?fields=status_code&access_token={urllib.parse.quote(TOKEN)}", timeout=60) as r:
        return json.load(r).get("status_code")

def wait_ready(cid):
    for _ in range(40):
        s = status(cid)
        if s == "FINISHED": return
        if s == "ERROR": raise RuntimeError(f"container ERROR {cid}")
        time.sleep(6)
    raise RuntimeError(f"timeout {cid}")

def media_url(a): return f"{BASE}/{a}"

for post in due:
    try:
        if DRY:
            # valida que as artes estao acessiveis, sem publicar
            for a in post["assets"]:
                with urllib.request.urlopen(media_url(a), timeout=60) as r:
                    assert r.status == 200
            print(f"  DRY-OK {post['date']} {post['type']} ({len(post['assets'])} arte/s) — artes acessiveis, NAO publicado")
            continue
        if post["type"] == "story":
            for a in post["assets"]:
                vid = a.lower().endswith(".mp4")
                c = api(f"{IG_USER}/media", {"media_type": "STORIES", ("video_url" if vid else "image_url"): media_url(a), "access_token": TOKEN})
                wait_ready(c["id"])
                pub = api(f"{IG_USER}/media_publish", {"creation_id": c["id"], "access_token": TOKEN})
                print(f"  PUBLICADO story {a} -> {pub['id']}")
            continue
        if post["type"] == "reel":
            c = api(f"{IG_USER}/media", {"media_type": "REELS", "video_url": media_url(post["assets"][0]), "caption": post["caption"], "share_to_feed": "true", "access_token": TOKEN})
            wait_ready(c["id"]); cid = c["id"]
        elif post["type"] == "carousel":
            kids = []
            for a in post["assets"]:
                vid = a.lower().endswith(".mp4")
                if vid:
                    c = api(f"{IG_USER}/media", {"media_type": "VIDEO", "is_carousel_item": "true", "video_url": media_url(a), "access_token": TOKEN}); wait_ready(c["id"])
                else:
                    c = api(f"{IG_USER}/media", {"image_url": media_url(a), "is_carousel_item": "true", "access_token": TOKEN})
                kids.append(c["id"])
            c = api(f"{IG_USER}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": post["caption"], "access_token": TOKEN}); cid = c["id"]
        else:
            c = api(f"{IG_USER}/media", {"image_url": media_url(post["assets"][0]), "caption": post["caption"], "access_token": TOKEN}); cid = c["id"]
        pub = api(f"{IG_USER}/media_publish", {"creation_id": cid, "access_token": TOKEN})
        print(f"  PUBLICADO {post['type']} {post['date']} -> {pub['id']}")
    except Exception as e:
        print(f"  ERRO {post['date']} {post['type']}: {e}")
