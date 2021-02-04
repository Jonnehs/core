"""Component to embed TP-Link smart home devices."""
import logging

from homeassistant import config_entries
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import SmartDevices, async_discover_devices, get_static_devices
from .const import (
    ATTR_CONFIG,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_RETRY_DELAY,
    CONF_RETRY_MAX_ATTEMPTS,
    CONF_SWITCH,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigType):
    """Set up TPLink from a config entry."""
    config_data = config_entry.data

    # These will contain the initialized devices
    lights = hass.data[DOMAIN][CONF_LIGHT] = []
    switches = hass.data[DOMAIN][CONF_SWITCH] = []

    # Add static devices
    static_devices = SmartDevices()
    if config_data is not None:
        static_devices = get_static_devices(config_data)

        lights.extend(static_devices.lights)
        switches.extend(static_devices.switches)

        hass.data[DOMAIN][CONF_RETRY_DELAY] = config_data[CONF_RETRY_DELAY]
        hass.data[DOMAIN][CONF_RETRY_MAX_ATTEMPTS] = config_data[
            CONF_RETRY_MAX_ATTEMPTS
        ]
    hass.data[DOMAIN]["add_attempt"] = 0

    # Add discovered devices
    if config_data is None or config_data[CONF_DISCOVERY]:
        discovered_devices = await async_discover_devices(hass, static_devices)

        lights.extend(discovered_devices.lights)
        switches.extend(discovered_devices.switches)

    forward_setup = hass.config_entries.async_forward_entry_setup
    if lights:
        _LOGGER.debug(
            "Got %s lights: %s", len(lights), ", ".join([d.host for d in lights])
        )
        hass.async_create_task(forward_setup(config_entry, "light"))
    if switches:
        _LOGGER.debug(
            "Got %s switches: %s", len(switches), ", ".join([d.host for d in switches])
        )
        hass.async_create_task(forward_setup(config_entry, "switch"))

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_lights = remove_switches = False
    if hass.data[DOMAIN][CONF_LIGHT]:
        remove_lights = await forward_unload(entry, "light")
    if hass.data[DOMAIN][CONF_SWITCH]:
        remove_switches = await forward_unload(entry, "switch")

    if remove_lights or remove_switches:
        hass.data[DOMAIN].clear()
        return True

    # We were not able to unload the platforms, either because there
    # were none or one of the forward_unloads failed.
    return False
