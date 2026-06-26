# Wiener Luft

Wiener Luft is a community-maintained Home Assistant integration that provides public air-quality and weather measurements from the Wiener Luftmessnetz using open government data published by the City of Vienna (MA 22).

[Home Assistant](https://www.home-assistant.io) is a free and open-source home automation platform that combines data from smart home devices and online services into a single system. This integration imports official air-quality and weather measurements from the City of Vienna into Home Assistant, where they can be used in dashboards, automations, historical analysis, and personalized alerts.

Although these measurements have been publicly available for many years, modern tools for exploring and integrating them remain surprisingly rare. The City of Vienna’s official information pages, for example, still refer users to a telephone recording service for current ozone measurements.

The integration uses the City of Vienna open data datasets [Luftmessnetz: aktuelle Messdaten Wien](https://www.data.gv.at/katalog/datasets/d9ae1245-158e-4d79-86a4-2d9b3defbedc) and [Luftmessnetz: Meteorologie Standorte Wien](https://www.data.gv.at/katalog/datasets/f2bb4f42-2c40-4c9d-890b-c2b3061bfe5a). It provides measurements from 18 monitoring stations across Vienna and requires no credentials or API keys.

Available measurements include particulate matter (PM10, PM2.5), nitrogen dioxide (NO₂), nitrogen oxides (NOₓ), ozone (O₃), sulphur dioxide (SO₂), carbon monoxide (CO), air temperature, relative humidity, wind speed, and wind direction.

In Home Assistant, the integration creates sensors for each available monitoring station and measurement. These sensors update every 30 minutes and can be used like other Home Assistant sensors. 

Sensor names are localized in Home Assistant and currently available in English and German.

### Sensor behavior

If the data source publishes a new station or measurement, the integration adds the corresponding sensor automatically during a future refresh.

Air-quality sensors use the shortest averaging interval available in the source data for each pollutant. This is usually a 30-minute average, but longer averages are used when that is all the source provides.

## Installation

Home Assistant includes a curated catalog of official integrations. Community-maintained integrations such as Wiener Luft are installed separately through [HACS](https://www.hacs.xyz/) or by copying the integration files manually.

### Requirements

This integration requires Home Assistant 2026.3 or newer.

### HACS (recommended)

HACS, the Home Assistant Community Store, is the recommended installation method. If HACS is not installed yet, follow the [HACS installation guide](https://www.hacs.xyz/docs/use/) before continuing.

1. Add `https://github.com/alexostleitner/homeassistant-wiener-luft` as a HACS custom repository of type `Integration`.
2. Install `Wiener Luft` from HACS.
3. Restart Home Assistant.
4. Add the integration via `Settings` -> `Devices & services`.

### Manual installation

Copy the `wiener_luft` folder from `custom_components` into your Home Assistant `custom_components` directory, restart Home Assistant, and add `Wiener Luft` via `Settings` -> `Devices & services`. No `configuration.yaml` entry is required.

## Disclaimer and License

This project is not affiliated with, endorsed by, or maintained by the City of Vienna (Stadt Wien). 

Licensed under the MIT License. See `LICENSE` for details.
