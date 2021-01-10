"""Support for Adafruit DHT temperature and humidity sensor."""
from datetime import timedelta
import logging

import adafruit_dht
import board
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    PERCENTAGE,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

_LOGGER = logging.getLogger(__name__)

CONF_PIN = "pin"
CONF_SENSOR = "sensor"
CONF_HUMIDITY_OFFSET = "humidity_offset"
CONF_TEMPERATURE_OFFSET = "temperature_offset"

DEFAULT_NAME = "DHT Sensor"

# DHT11 is able to deliver data once per second, DHT22 once every two
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

SENSOR_TEMPERATURE = "temperature"
SENSOR_HUMIDITY = "humidity"
SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ["Temperature", None],
    SENSOR_HUMIDITY: ["Humidity", PERCENTAGE],
}


def validate_pin_input(value):
    """Validate that the GPIO PIN is prefixed with a D."""
    try:
        int(value)
        return f"D{value}"
    except ValueError:
        return value.upper()


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SENSOR): cv.string,
        vol.Required(CONF_PIN): vol.All(cv.string, validate_pin_input),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TEMPERATURE_OFFSET, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=-100, max=100)
        ),
        vol.Optional(CONF_HUMIDITY_OFFSET, default=0): vol.All(
            vol.Coerce(float), vol.Range(min=-100, max=100)
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the DHT sensor."""

    SENSOR_TYPES[SENSOR_TEMPERATURE][1] = hass.config.units.temperature_unit
    available_sensors = {
        "AM2302": adafruit_dht.DHT22,
        "DHT11": adafruit_dht.DHT11,
        "DHT22": adafruit_dht.DHT22,
    }
    sensor = available_sensors.get(config[CONF_SENSOR])
    pin = config[CONF_PIN]
    temperature_offset = config[CONF_TEMPERATURE_OFFSET]
    humidity_offset = config[CONF_HUMIDITY_OFFSET]
    name = config[CONF_NAME]

    if not sensor:
        _LOGGER.error("DHT sensor type is not supported")
        return False

    data = DHTClient(sensor, pin, name)
    dev = []

    try:
        for variable in config[CONF_MONITORED_CONDITIONS]:
            dev.append(
                DHTSensor(
                    data,
                    variable,
                    SENSOR_TYPES[variable][1],
                    name,
                    temperature_offset,
                    humidity_offset,
                )
            )
    except KeyError:
        pass

    add_entities(dev, True)


class DHTSensor(Entity):
    """Implementation of the DHT sensor."""

    def __init__(
        self,
        dht_client,
        sensor_type,
        temp_unit,
        name,
        temperature_offset,
        humidity_offset,
    ):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.dht_client = dht_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self.temperature_offset = temperature_offset
        self.humidity_offset = humidity_offset
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the DHT and updates the states."""
        self.dht_client.update()
        temperature_offset = self.temperature_offset
        humidity_offset = self.humidity_offset
        data = self.dht_client.data

        if self.type == SENSOR_TEMPERATURE and SENSOR_TEMPERATURE in data:
            temperature = data[SENSOR_TEMPERATURE]
            _LOGGER.debug(
                "Temperature %.1f \u00b0C + offset %.1f",
                temperature,
                temperature_offset,
            )
            if -20 <= temperature < 80:
                self._state = round(temperature + temperature_offset, 1)
                if self.temp_unit == TEMP_FAHRENHEIT:
                    self._state = round(celsius_to_fahrenheit(temperature), 1)
        elif self.type == SENSOR_HUMIDITY and SENSOR_HUMIDITY in data:
            humidity = data[SENSOR_HUMIDITY]
            _LOGGER.debug("Humidity %.1f%% + offset %.1f", humidity, humidity_offset)
            if 0 <= humidity <= 100:
                self._state = round(humidity + humidity_offset, 1)


class DHTClient:
    """Get the latest data from the DHT sensor."""

    def __init__(self, sensor, pin, name):
        """Initialize the sensor."""
        self.sensor = sensor
        self.pin = getattr(board, pin)
        self.data = {}
        self.name = name

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data the DHT sensor."""
        dht = self.sensor(self.pin)
        try:
            humidity = dht.humidity
            temperature = dht.temperature
            if temperature:
                self.data[SENSOR_TEMPERATURE] = temperature
            if humidity:
                self.data[SENSOR_HUMIDITY] = humidity
        except RuntimeError:
            _LOGGER.debug("Unexpected value from DHT sensor: %s", self.name)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error updating DHT sensor: %s", self.name)
        finally:
            dht.exit()
