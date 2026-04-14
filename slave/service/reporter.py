import websockets
import json
import asyncio

from config import ConfigService
from .metrics.collector import MetricsCollector


class GatewayReporter:
    """
    Maintains a persistent outbound WebSocket connection to the Gateway and
    pushes a metrics snapshot every PUSH_INTERVAL seconds.

    Disabled entirely when GATEWAY_WS_URL is not set — safe to deploy slaves
    that don't have a gateway yet.
    """

    def __init__(self, log, config: ConfigService, collector: MetricsCollector):
        self.collector = collector
        self.enabled = bool(config.GATEWAY_WS_URL)
        self.config = config
        self.log = log

    async def run(self) -> None:
        if not self.enabled:
            self.log.info(
                "[GatewayReporter] GATEWAY_WS_URL not set — reporter disabled."
            )
            return

        while True:
            try:
                await self._connect_and_push()
            except asyncio.CancelledError:
                self.log.info("[GatewayReporter] Cancelled.")
                raise
            except Exception as exc:
                delay = getattr(self.config, "RECONNECT_DELAY", 5) or 5
                self.log.warning(
                    "[GatewayReporter] Unexpected error: %s. Reconnecting in %ds…",
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

    async def _connect_and_push(self) -> None:
        gateway_url = self.config.GATEWAY_WS_URL
        self.log.info("[GatewayReporter] Connecting to %s", gateway_url)
        self.log.info("[GatewayReporter] Config GATEWAY_WS_URL value: %s", gateway_url)

        async with websockets.connect(
            gateway_url,
            ping_interval=20,
            ping_timeout=10,
            open_timeout=10,
        ) as ws:
            self.log.info("[GatewayReporter] Connected as %s", self.collector.node_id)

            # Registration frame
            await ws.send(
                json.dumps(
                    {
                        "event": "hello",
                        "node_id": self.collector.node_id,
                        "type": self.collector.node_type,
                    }
                )
            )

            while True:
                payload = self.collector.collect()
                await ws.send(json.dumps(payload))
                self.log.debug(
                    "[GatewayReporter] Pushed snapshot for %s", self.collector.node_id
                )
                await asyncio.sleep(self.config.PUSH_INTERVAL)
