import logging
from datetime import datetime, timezone
from typing import Optional
from app.services.http_client import http_client
from app.config import settings

logger = logging.getLogger("scanner.currency")

class CurrencyService:
    """
    Real-time Currency Exchange Rate Service.
    Automatically fetches official live FX rates (European Central Bank / Frankfurter API)
    so conversions between USD and EUR are never hardcoded.
    """

    def __init__(self):
        self.usd_to_eur_rate: float = settings.USD_TO_EUR_RATE
        self.last_updated: Optional[datetime] = None
        self._is_fetching: bool = False

    async def fetch_live_rate(self) -> float:
        """Fetches live USD to EUR exchange rate from public ECB-backed API."""
        endpoints = [
            "https://api.frankfurter.dev/v1/latest?from=USD&to=EUR",
            "https://open.er-api.com/v6/latest/USD"
        ]

        for url in endpoints:
            try:
                resp = await http_client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    rates = data.get("rates", {})
                    eur_rate = rates.get("EUR")
                    if eur_rate and isinstance(eur_rate, (int, float)) and eur_rate > 0:
                        self.usd_to_eur_rate = float(eur_rate)
                        self.last_updated = datetime.now(timezone.utc)
                        logger.info(f"✅ Tipo de cambio en vivo actualizado: 1 USD = {self.usd_to_eur_rate:.4f} EUR")
                        return self.usd_to_eur_rate
            except Exception as e:
                logger.warning(f"No se pudo obtener tipo de cambio desde '{url}': {e}")

        logger.info(f"Usando tipo de cambio actual: 1 USD = {self.usd_to_eur_rate:.4f} EUR")
        return self.usd_to_eur_rate

    def get_rate(self) -> float:
        return self.usd_to_eur_rate

    def usd_cents_to_eur_cents(self, usd_cents: int) -> int:
        """Converts USD cents to EUR cents with accurate integer rounding."""
        if usd_cents <= 0:
            return 0
        return int(round(usd_cents * self.usd_to_eur_rate))

    def usd_to_eur(self, usd_amount: float) -> float:
        """Converts USD float to EUR float."""
        return round(usd_amount * self.usd_to_eur_rate, 2)

currency_service = CurrencyService()
