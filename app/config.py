# app/config.py
import os
from dotenv import load_dotenv
from pydantic import BaseSettings, Field

load_dotenv()

class Settings(BaseSettings):
    hyperliquid_private_key: str = Field(..., env='HYPERLIQUID_PRIVATE_KEY')
    hyperliquid_account_address: str = Field(..., env='HYPERLIQUID_ACCOUNT_ADDRESS')
    hyperliquid_monitoring_address: str = Field(..., env='HYPERLIQUID_MONITORING_ADDRESS')
    asset_name: str = 'ETH'
    leverage: int = 5
    is_cross: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    class Config:
        env_file = ".env"

settings = Settings()
