# Wiener Luft

Wiener Luft is a community-maintained Home Assistant integration that imports public air-quality and weather measurements from the Vienna Air Quality Monitoring Network (Wiener Luftmessnetz) using open government data published by the City of Vienna (MA 22).

[Home Assistant](https://www.home-assistant.io) is a free and open-source home automation platform that combines data from smart home devices and online services into a single system. This integration adds official air-quality and weather measurements from the City of Vienna, making them available for dashboards, automations, historical analysis, and personalized alerts.

Although these measurements have been publicly available for many years, modern tools for exploring and integrating them remain surprisingly rare. For example, the City of Vienna’s official information pages still mention a telephone recording service for current ozone measurements.

The integration uses the City of Vienna open data datasets [Luftmessnetz: aktuelle Messdaten Wien](https://www.data.gv.at/katalog/datasets/d9ae1245-158e-4d79-86a4-2d9b3defbedc) and [Luftmessnetz: Meteorologie Standorte Wien](https://www.data.gv.at/katalog/datasets/f2bb4f42-2c40-4c9d-890b-c2b3061bfe5a). It provides measurements from 18 monitoring stations across Vienna and requires neither credentials nor API keys.

Available measurements include particulate matter (PM10, PM2.5), nitrogen dioxide (NO₂), nitrogen oxides (NOₓ), ozone (O₃), sulphur dioxide (SO₂), carbon monoxide (CO), air temperature, relative humidity, wind speed, and wind direction. Monitoring stations differ in the parameters they measure because each location is equipped with different instruments. As a result, the available sensor types vary between stations.

During setup, users select which monitoring stations and measurement types they want to include. The integration creates Home Assistant sensors for every selected combination that is available in the source data. The created sensors update every 30 minutes and behave like any other Home Assistant sensor.

Sensor names are localized in Home Assistant and currently available in English and German.

Data availability, completeness, and correctness depend entirely on the published source data. Individual monitoring stations may occasionally report missing values, delayed updates, or corrected measurements.

### Sensor behavior

If the data source starts publishing a new monitoring station or a new measurement for an existing station that is not part of the saved configuration snapshot, the integration logs a daily notice after the next successful station refresh. Open the options flow and save the configuration again to update the snapshot.

Air-quality sensors use the shortest averaging interval available in the source data for each pollutant. This is usually a 30-minute average, but longer averages are used when no shorter average is available.

## Installation

Home Assistant includes a curated catalog of official integrations. Community-maintained integrations such as Wiener Luft are installed separately, usually through [HACS](https://www.hacs.xyz/). Manual installation is also possible.

### Requirements

Wiener Luft requires Home Assistant 2026.3 or newer.

### HACS (recommended)

[HACS](https://www.hacs.xyz/) is the recommended installation method for community-maintained Home Assistant integrations. If HACS is not installed yet, follow the [HACS installation guide](https://www.hacs.xyz/docs/use/) first.

1. Add `https://github.com/alexostleitner/homeassistant-wiener-luft` as a HACS custom repository of type `Integration`.
2. Install `Wiener Luft` from HACS.
3. Restart Home Assistant.
4. Go to `Settings` -> `Devices & services` and add `Wiener Luft`.

### Manual installation

Copy the `wiener_luft` folder from `custom_components` into the `custom_components` directory of your Home Assistant installation. Restart Home Assistant, then go to `Settings` -> `Devices & services` and add `Wiener Luft`.

No `configuration.yaml` entry is required.

## Reporting Issues

When reporting an issue, include the Home Assistant version, the installed Wiener Luft version, the relevant error log, and the steps needed to reproduce the problem. For UI-related issues, include a screenshot where possible.

## Disclaimer and License

This project is not affiliated with, endorsed by, or maintained by the City of Vienna (Stadt Wien). It reads and processes publicly available datasets published by the City of Vienna.

Wiener Luft is licensed under the MIT License. See `LICENSE` for details.

The source datasets are published by the City of Vienna as Open Government Data under the Creative Commons Attribution 4.0 International (CC BY 4.0) license.
