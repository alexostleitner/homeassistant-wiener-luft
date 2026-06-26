from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "wiener_luft"
NAME = "Wiener Luft"

PLATFORMS = [Platform.SENSOR]

MEASUREMENTS_URL = "https://www.wien.gv.at/ma22-lgb/umweltgut/lumesakt-v2.csv"
STATIONS_URL = (
    "https://data.wien.gv.at/daten/geo?service=WFS&request=GetFeature&"
    "version=1.1.0&typeName=ogdwien:LUFTGUETENETZOGD&srsName=EPSG:4326&"
    "outputFormat=json"
)

MEASUREMENT_UPDATE_INTERVAL = timedelta(minutes=30)
STATION_UPDATE_INTERVAL = timedelta(days=1)
HTTP_TIMEOUT_SECONDS = 20
