"""Pi-hole v6 DNS switching for baluhost.local."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class PiholeClient:
    """Pi-hole v6 REST API client with session-based auth."""

    def __init__(
        self,
        base_url: str | None = None,
        password: str | None = None,
    ):
        self._base_url = (base_url or settings.pihole_url).rstrip("/") + "/api"
        self._password = password or settings.pihole_password
        self._sid: str | None = None

    async def _auth(self) -> str:
        """Get session ID (SID) from Pi-hole."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self._base_url}/auth",
                json={"password": self._password},
            )
            resp.raise_for_status()
            data = resp.json()
            self._sid = data["session"]["sid"]
            return self._sid

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Authenticated request with auto-retry on 401."""
        if not self._sid:
            await self._auth()

        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"sid": self._sid}
            resp = await client.request(
                method, f"{self._base_url}{path}",
                headers=headers, **kwargs,
            )
            if resp.status_code == 401:
                await self._auth()
                headers = {"sid": self._sid}
                resp = await client.request(
                    method, f"{self._base_url}{path}",
                    headers=headers, **kwargs,
                )
            resp.raise_for_status()
            return resp.json()

    async def set_dns_host(self, ip: str, hostname: str) -> None:
        """Add/update a local DNS A record."""
        encoded = f"{ip} {hostname}".replace(" ", "%20")
        await self._request("PUT", f"/config/dns/hosts/{encoded}")

    async def remove_dns_host(self, ip: str, hostname: str) -> None:
        """Remove a local DNS A record."""
        encoded = f"{ip} {hostname}".replace(" ", "%20")
        try:
            await self._request("DELETE", f"/config/dns/hosts/{encoded}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise

    async def switch_baluhost_dns(self, target_ip: str) -> bool:
        """Switch baluhost.local to point to target_ip.

        Returns True on success, False on failure.
        """
        if settings.is_dev_mode:
            logger.info("[DEV] DNS switch: baluhost.local -> %s (not executed)", target_ip)
            return True

        hostname = "baluhost.local"
        try:
            # Remove old records for both NAS and Pi IPs
            for ip in (settings.nas_ip, settings.pi_ip):
                if ip:
                    try:
                        await self.remove_dns_host(ip, hostname)
                    except Exception:
                        pass  # May not exist

            # Add new record
            await self.set_dns_host(target_ip, hostname)
            logger.info("DNS switched: %s -> %s", hostname, target_ip)
            return True
        except Exception as e:
            logger.error("DNS switch failed: %s", e)
            return False
