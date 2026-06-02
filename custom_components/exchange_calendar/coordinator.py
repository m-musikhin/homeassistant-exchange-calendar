"""DataUpdateCoordinator for Exchange Calendar."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_DAYS_TO_FETCH,
    CONF_MAX_EVENTS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_DAYS_TO_FETCH,
    DEFAULT_MAX_EVENTS,
    DEFAULT_UPDATE_INTERVAL,
)
from .exchange_client import ExchangeClient, ExchangeConnectionError, ExchangeAuthError

_LOGGER = logging.getLogger(__name__)


class ExchangeCalendarCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator for periodic Exchange calendar event fetching.

    Equivalent to MMM-Exchange scheduleNextFetch(), using HA's
    DataUpdateCoordinator infrastructure.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: ExchangeClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        interval = config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(minutes=interval),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch events from Exchange server.

        exchangelib is synchronous, so we run it via async_add_executor_job.
        """
        days = self.config_entry.options.get(
            CONF_DAYS_TO_FETCH, DEFAULT_DAYS_TO_FETCH
        )
        max_events = self.config_entry.options.get(
            CONF_MAX_EVENTS, DEFAULT_MAX_EVENTS
        )

        try:
            return await self.hass.async_add_executor_job(
                self.client.get_events, days, max_events
            )
        except ExchangeAuthError as err:
            # Trigger the reauth flow so the user can update the (likely expired)
            # password without removing and re-adding the integration.
            raise ConfigEntryAuthFailed(
                f"Exchange authentication error: {err}"
            ) from err
        except ExchangeConnectionError as err:
            raise UpdateFailed(
                f"Exchange server unreachable: {err}"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Exchange events")
            raise UpdateFailed(f"Unexpected error: {err}") from err
