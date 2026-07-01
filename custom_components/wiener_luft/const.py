from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "wiener_luft"
NAME = "Wiener Luft"
CONF_STATIONS = "stations"
CONF_MEASUREMENTS = "measurements"
SOURCE_SNAPSHOT = "_source_snapshot"
STATION_SNAPSHOT = "_station_snapshot"

PLATFORMS = [Platform.SENSOR]

MEASUREMENTS_URL = "https://www.wien.gv.at/ma22-lgb/umweltgut/lumesakt-v2.csv"
STATIONS_URL = (
    "https://data.wien.gv.at/daten/geo?service=WFS&request=GetFeature&"
    "version=1.1.0&typeName=ogdwien:LUFTGUETENETZOGD&srsName=EPSG:4326&"
    "outputFormat=json"
)

MEASUREMENT_UPDATE_INTERVAL = timedelta(minutes=30)
STATION_UPDATE_INTERVAL = timedelta(days=1)
STALE_AFTER = timedelta(hours=2)
HTTP_TIMEOUT_SECONDS = 20
CALM_WIND_SPEED_MPS = 0.5
