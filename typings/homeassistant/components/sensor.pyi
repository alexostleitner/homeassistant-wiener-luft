from typing import Any

class SensorDeviceClass:
    PM25: str
    PM10: str
    NITROGEN_DIOXIDE: str
    OZONE: str
    SULPHUR_DIOXIDE: str
    CO: str
    TEMPERATURE: str
    HUMIDITY: str
    WIND_SPEED: str
    WIND_DIRECTION: str

class SensorStateClass:
    MEASUREMENT: str
    MEASUREMENT_ANGLE: str

class SensorEntity:
    _attr_has_entity_name: bool
    _attr_should_poll: bool
    _attr_state_class: str | None
    _attr_translation_key: str | None
    _attr_device_class: str | None
    _attr_icon: str | None
    _attr_suggested_display_precision: int | None
    _attr_unique_id: str | None
    _attr_device_info: Any

    def async_write_ha_state(self) -> None: ...
