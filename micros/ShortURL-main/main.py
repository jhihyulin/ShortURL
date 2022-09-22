# db
from deta import Deta
# webserver
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# for make short url
import hashlib
import time
from urllib.parse import urlunparse, urlparse
import lib.base62 as Base62
# env
import os
from dotenv import load_dotenv

# env variable
load_dotenv()
PROJECTING_KEY = os.getenv('DETA_PROJECT_KEY')
SERVER_PREFIX = os.getenv('SERVER_PREFIX')

# init database
deta = Deta(PROJECTING_KEY)
DB = deta.Base("db")
# init webserver
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def short(url):
    # MD5 hash and take first 40bit encdoe with Base62
    return Base62.encodebytes(hashlib.md5(url.encode('utf-8')).digest()[-5:])


def use_rand_key(url_key):
    # use random key
    result = Base62.encodebytes(hashlib.md5(
        str(time.time()).encode('utf-8')).digest()[-5:])
    if result != url_key:
        return result
    else:
        return use_rand_key(url_key)


class Create_short_url(BaseModel):
    original_url: str


@app.post("/create")
def shorten_request(data: Create_short_url):
    """
    Get the shorten request from client.
    """
    if urlparse(data.original_url).scheme == "":
        raise HTTPException(
            status_code=400, detail="URL should have a scheme")
    url = data.original_url
    url_key = short(url)
    timestamp = time.time()
    timestring = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
    if DB.get(url_key) == None:
        DB.put(
            {
                "original_url": data.original_url,
                "timestamp": timestamp,
                "timestring": timestring,
                "create_method": "hash",
                "used_count": 0
            }, url_key
        )
        return {"url": SERVER_PREFIX + url_key}
    elif DB.get(url_key) != None and DB.get(url_key)["original_url"] != data.original_url:
        url_key = use_rand_key(url_key)
        DB.put(
            {
                "original_url": data.original_url,
                "timestamp": timestamp,
                "timestring": timestring,
                "create_method": "rand",
                "used_count": 0
            }, url_key
        )
        return {"url": SERVER_PREFIX + url_key}
    elif DB.get(url_key) != None and DB.get(url_key)["original_url"] == data.original_url:
        return {"url": SERVER_PREFIX + url_key}


@app.get("/{url_key}")
def redirect_to_url(url_key):
    """
    Check the url_key is in DB, redirect to original url.
    """
    data = DB.get(url_key)
    if data is None:
        raise HTTPException(status_code=404, detail="Key not found")
    else:
        used_count = data["used_count"] + 1
        original_url = data["original_url"]
        DB.put(
            {
                "original_url": data["original_url"],
                "timestamp": data["timestamp"],
                "timestring": data["timestring"],
                "create_method": data["create_method"],
                "used_count": used_count
            }, url_key
        )
        return RedirectResponse(original_url)
