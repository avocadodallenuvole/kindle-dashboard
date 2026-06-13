#!/usr/bin/env python3
"""
Kindle e-ink desk dashboard generator.
600x800 grayscale PNG: date + Milan weather + latest AI/wearable/health-tech news.
For a jailbroken Kindle Touch (D01200) via OnlineScreensaver.

Data (open-meteo weather + Google News RSS) is fetched live at runtime.
Designed to run on GitHub Actions and publish the PNG to GitHub Pages.
"""

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
import os
import re

W, H = 600, 800
MARGIN = 44
TZ = ZoneInfo("Europe/Rome")
LAT, LON = 45.4642, 9.19  # Milano

# News topics (Google News RSS query). Edit to taste.
NEWS_QUERY = '("artificial intelligence" OR wearable OR "health tech")'
NEWS_LANG = ("en-US", "US", "US:en")   # (hl, gl, ceid) -> set to it for Italian
NEWS_COUNT = 4

DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì",
          "Venerdì", "Sabato", "Domenica"]
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

WMO = {0: "Sereno", 1: "Quasi sereno", 2: "Parz. nuvoloso", 3: "Coperto",
       45: "Nebbia", 48: "Nebbia", 51: "Pioviggine", 53: "Pioviggine",
       55: "Pioviggine", 61: "Pioggia", 63: "Pioggia", 65: "Pioggia forte",
       66: "Pioggia gelata", 67: "Pioggia gelata", 71: "Neve", 73: "Neve",
       75: "Neve forte", 77: "Nevischio", 80: "Rovesci", 81: "Rovesci",
       82: "Rovesci forti", 85: "Rovesci di neve", 86: "Rovesci di neve",
       95: "Temporale", 96: "Temporale", 99: "Temporale"}


def get_weather():
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={LAT}&longitude={LON}"
           "&current=temperature_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code"
           "&timezone=Europe/Rome&forecast_days=2")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            d = json.load(r)
        return {"now": round(d["current"]["temperature_2m"]),
                "now_code": d["current"]["weather_code"],
                "tmax": round(d["daily"]["temperature_2m_max"][0]),
                "tmin": round(d["daily"]["temperature_2m_min"][0]),
                "tmax2": round(d["daily"]["temperature_2m_max"][1]),
                "tmin2": round(d["daily"]["temperature_2m_min"][1]),
                "code2": d["daily"]["weather_code"][1], "live": True}
    except Exception:
        return {"now": 23, "now_code": 1, "tmax": 26, "tmin": 15,
                "tmax2": 24, "tmin2": 14, "code2": 2, "live": False}


def get_news():
    hl, gl, ceid = NEWS_LANG
    q = urllib.parse.quote(NEWS_QUERY)
    url = (f"https://news.google.com/rss/search?q={q}+when:2d"
           f"&hl={hl}&gl={gl}&ceid={ceid}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            root = ET.fromstring(r.read())
        items = []
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            if not title:
                continue
            source = ""
            m = re.search(r"\s-\s([^-]+)$", title)
            if m:
                source = m.group(1).strip()
                title = title[:m.start()].strip()
            items.append((title, source))
            if len(items) >= NEWS_COUNT:
                break
        if items:
            return items, True
    except Exception:
        pass
    sample = [
        ("OpenAI unveils new on-device model for wearables", "The Verge"),
        ("Apple Watch adds blood-pressure trend tracking", "9to5Mac"),
        ("Startup raises $40M for AI-powered health monitoring ring", "TechCrunch"),
        ("EU drafts rules for medical AI and wearable data", "Reuters"),
    ]
    return sample, False


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(d, text, fnt, maxw, max_lines):
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if line and d.textlength(test, font=fnt) > maxw:
            lines.append(line)
            line = w
            if len(lines) == max_lines:
                line = ""
                break
        else:
            line = test
    if line and len(lines) < max_lines:
        lines.append(line)
    rendered = sum(len(l.split()) for l in lines)
    if rendered < len(words) and lines:
        last = lines[-1]
        while last and d.textlength(last + " …", font=fnt) > maxw:
            last = last[:-1].rstrip()
        lines[-1] = last + " …"
    return lines


def main():
    now = datetime.now(TZ)
    wx = get_weather()
    news, news_live = get_news()

    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    f_big = font(DEJAVU_BOLD, 84)
    f_date = font(DEJAVU, 30)
    f_label = font(DEJAVU_BOLD, 19)
    f_temp = font(DEJAVU_BOLD, 92)
    f_cond = font(DEJAVU, 28)
    f_sub = font(DEJAVU, 25)
    f_news = font(DEJAVU_BOLD, 24)
    f_src = font(DEJAVU, 19)
    f_foot = font(DEJAVU, 19)
    innerw = W - 2 * MARGIN

    def label(txt, y):
        d.text((MARGIN, y), txt.upper(), font=f_label, fill=115)

    # header
    y = 42
    d.text((MARGIN, y), GIORNI[now.weekday()], font=f_big, fill=0)
    y += 100
    d.text((MARGIN, y), f"{now.day} {MESI[now.month]} {now.year}",
           font=f_date, fill=70)

    # weather
    y += 54
    d.line((MARGIN, y, W - MARGIN, y), fill=185, width=2)
    y += 22
    label("Milano", y)
    y += 28
    d.text((MARGIN, y), f"{wx['now']}°", font=f_temp, fill=0)
    d.text((MARGIN + 200, y + 18), WMO.get(wx["now_code"], ""),
           font=f_cond, fill=0)
    d.text((MARGIN + 200, y + 54), f"max {wx['tmax']}°  min {wx['tmin']}°",
           font=f_sub, fill=70)
    y += 108
    d.text((MARGIN, y),
           f"Domani  {wx['tmax2']}°/{wx['tmin2']}°  ·  {WMO.get(wx['code2'],'')}",
           font=f_sub, fill=70)

    # news
    y += 50
    d.line((MARGIN, y, W - MARGIN, y), fill=185, width=2)
    y += 22
    label("Ultime · AI · Wearable · Health", y)
    y += 34
    for title, source in news:
        if y > H - 120:
            break
        lines = wrap(d, title, f_news, innerw - 22, 2)
        d.text((MARGIN, y + 4), "›", font=f_news, fill=0)
        for ln in lines:
            d.text((MARGIN + 22, y), ln, font=f_news, fill=0)
            y += 30
        if source:
            d.text((MARGIN + 22, y), source, font=f_src, fill=120)
            y += 26
        y += 12

    # footer
    upd = now.strftime("%H:%M")
    tags = []
    if not wx["live"]:
        tags.append("meteo demo")
    if not news_live:
        tags.append("news demo")
    tag = ("  (" + ", ".join(tags) + ")") if tags else ""
    d.line((MARGIN, H - 64, W - MARGIN, H - 64), fill=215, width=1)
    d.text((MARGIN, H - 48), f"aggiornato {upd}  ·  Milano{tag}",
           font=f_foot, fill=125)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "dashboard.png")
    img.save(out)
    print("saved", out, "weather_live=", wx["live"], "news_live=", news_live)


if __name__ == "__main__":
    main()
