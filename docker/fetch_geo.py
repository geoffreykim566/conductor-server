"""Image build step: download the DB-IP Lite country database (CC BY 4.0) to /opt/geo.
This month's file, else last month's. A failure leaves no file and doesn't fail the build:
the server runs and countries are unknown (app/core/geo.py)."""
import datetime as d
import gzip
import os
import urllib.request

os.makedirs("/opt/geo", exist_ok=True)
first = d.date.today().replace(day=1)
for month in (first, (first - d.timedelta(days=1)).replace(day=1)):
    url = f"https://download.db-ip.com/free/dbip-country-lite-{month:%Y-%m}.mmdb.gz"
    try:
        # Their CDN refuses the default Python-urllib agent (403).
        req = urllib.request.Request(url, headers={"User-Agent": "conductor-server-build"})
        data = gzip.decompress(urllib.request.urlopen(req, timeout=60).read())
        with open("/opt/geo/dbip-country-lite.mmdb", "wb") as f:
            f.write(data)
        print("geo:", url, len(data), "bytes")
        break
    except Exception as e:
        print("geo: failed", url, e)
