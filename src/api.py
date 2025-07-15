import logging
import re

import requests
from bs4 import BeautifulSoup
from cachetools import TTLCache, cached
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger("uvicorn.error")
# Separate caches for different functions
today_cache = TTLCache(maxsize=1, ttl=3600)
week_cache = TTLCache(maxsize=1, ttl=3600)

app = FastAPI()
templates = Jinja2Templates(directory="template")
regex = re.compile(r"spätzle <sup>([^/]*)</sup>", re.IGNORECASE)


@cached(today_cache)
def checkMensa():
    logger.info("Checking Mensa")

    try:
        url = "https://seezeit.com/essen/speiseplaene/mensa-giessberg/"
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")

        today = soup.find("a", class_="heute")["rel"][0]
        today_menu = soup.find("div", id=f"tab{today}")
        meals = today_menu.find_all("div", class_="title")

        spaetzle = None
        for m in meals:
            if "spätzle" in m.text.lower():
                spaetzle = m
                break

        if spaetzle is not None:
            ingredients = re.search(regex, str(spaetzle)).group(1)
            if "28" in ingredients:
                answer = "Spätzle with egg today"
                color = "green"
                emoji = "✅"

            else:
                answer = "WARNING: Spätzle without egg today"
                color = "red"
                emoji = "❌"
        else:
            answer = "No Spätzle today "
            color = "grey"
            emoji = "🤷"
    except Exception:
        answer = "No menu today"
        color = "grey"
        emoji = "⛱️"
    finally:
        logger.info(f"Answer: {answer}, Color: {color}, Emoji: {emoji}")
        return answer, color, emoji


@cached(week_cache)
def checkMensaWeek():
    logger.info("Checking Mensa for the week")
    url = "https://seezeit.com/essen/speiseplaene/mensa-giessberg/"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    week_results = []
    # There are up to 12 tabs, check all available tabs
    for i in range(1, 12):
        # Find the tab element to get the date from the span
        tab = soup.find("a", class_=f"tab{i}")
        if not tab:
            continue

        # Extract the date from the span inside the tab
        span = tab.find("span")
        if span:
            day_name = span.get_text(strip=True)  # e.g., "Mo. 07.07."
        else:
            day_name = f"Day {i}"

        # Check if this is today's tab and add "(Today)" to the day name
        if "heute" in tab.get("class", []):
            day_name += " (Today)"

        menu = soup.find("div", id=f"tab{i}")
        if not menu:
            week_results.append(
                {"day": day_name, "text": "No menu", "color": "grey", "emoji": "🤷"}
            )
            continue
        meals = menu.find_all("div", class_="title")
        spaetzle = None
        for m in meals:
            if "Spätzle" in m.text:
                spaetzle = m
                break
        if spaetzle is not None:
            match = re.search(regex, str(spaetzle))
            ingredients = match.group(1) if match else ""
            if "28" in ingredients:
                answer = "Spätzle with egg"
                color = "green"
                emoji = "✅"
            else:
                answer = "WARNING: Spätzle without egg"
                color = "red"
                emoji = "❌"
        else:
            answer = "No Spätzle"
            color = "grey"
            emoji = "🤷"
        week_results.append(
            {"day": day_name, "text": answer, "color": color, "emoji": emoji}
        )
    # For backward compatibility, return today's result as before
    today_idx = int(soup.find("a", class_="heute")["rel"][0]) - 1
    today = (
        week_results[today_idx]
        if 0 <= today_idx < len(week_results)
        else {"text": "No Spätzle today", "color": "grey", "emoji": "🤷"}
    )
    print(week_results)
    return today["text"], today["color"], today["emoji"], week_results


@app.get("/weekly", response_class=HTMLResponse)
async def weekly(request: Request):
    answer, color, emoji, week = checkMensaWeek()
    return templates.TemplateResponse(
        request=request,
        name="main.html",
        context={"text": answer, "color": color, "emoji": emoji, "week": week},
    )


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    answer, color, emoji = checkMensa()
    return templates.TemplateResponse(
        request=request,
        name="main.html",
        context={"text": answer, "color": color, "emoji": emoji},
    )


@app.get("/manifest.json")
async def manifest(request: Request):
    return FileResponse(path="assets/manifest.json")


@app.get("/icons/512.png")
async def icon(request: Request):
    return FileResponse(path="assets/logo.png")
