import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys & URLs
    CSFLOAT_API_KEY: str = Field(default="", description="CSFloat Developer API Key")
    CSFLOAT_BASE_URL: str = Field(default="https://csfloat.com/api/v1", description="CSFloat API Base URL")
    STEAM_BASE_URL: str = Field(default="https://steamcommunity.com/market", description="Steam Market Base URL")

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./arbitrage.db", description="SQLAlchemy Database URL")

    # Scanner settings
    REFRESH_INTERVAL_SECONDS: int = Field(default=60, description="Scanner polling loop interval in seconds")
    MAX_DATA_AGE_SECONDS: int = Field(default=120, description="Seconds after which data is considered stale")
    MAX_CONCURRENT_REQUESTS: int = Field(default=2, description="Maximum concurrent external API requests")

    # Filter Defaults
    MIN_ROI_PERCENT: float = Field(default=10.0, description="Minimum ROI % to consider")
    MIN_PROFIT_USD: float = Field(default=1.00, description="Minimum gross profit in USD")
    MAX_SKIN_PRICE_USD: float = Field(default=1000.00, description="Maximum skin price in USD")
    MIN_STEAM_QUANTITY: int = Field(default=1, description="Minimum buy order quantity on Steam")

    # Currency & Conversion Settings (Unified in EUR)
    CURRENCY: str = Field(default="EUR", description="Display and calculation currency (EUR or USD)")
    CURRENCY_SYMBOL: str = Field(default="€", description="Currency symbol: € or $")
    STEAM_CURRENCY_ID: int = Field(default=3, description="Steam Currency ID: 3 for EUR, 1 for USD")
    STEAM_COUNTRY_CODE: str = Field(default="ES", description="Steam Country Code")
    USD_TO_EUR_RATE: float = Field(default=0.92, description="Conversion rate from USD to EUR")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

settings = Settings()
