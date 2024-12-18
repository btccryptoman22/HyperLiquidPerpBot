# app/exchange_manager.py
import logging
import threading
from eth_account import Account
from eth_account.signers.local import LocalAccount
from hyperliquid.exchange import Exchange
from hyperliquid.utils.constants import MAINNET_API_URL
from .logger import logger
from .config import settings

class ExchangeManager:
    def __init__(self):
        self.exchange = None
        self.exchange_initialized = False
        self.max_position_size = 0.0
        self.asset_name = settings.asset_name
        self.leverage = settings.leverage
        self.is_cross = settings.is_cross
        self.position_lock = threading.Lock()
        self.current_position = 'none'  # 'buy', 'sell', 'none'
        self.current_size = 0.0
        self.current_entry_px = 0.0
        self.initialize_exchange()

    def calculate_max_position_size(self):
        try:
            user_state = self.exchange.info.user_state(settings.hyperliquid_monitoring_address)
            margin_summary = user_state.get("marginSummary", {})
            account_value_str = margin_summary.get("accountValue", "0")
            account_value = float(account_value_str)

            if account_value <= 0:
                raise ValueError("証拠金が不足しています。")

            usable_margin = account_value * 0.9
            logger.info(f"使用可能証拠金（90%）: ${usable_margin:.2f}")

            all_mids = self.exchange.info.all_mids()
            price_str = all_mids.get(self.asset_name, "0")
            price = float(price_str)
            if price == 0:
                raise ValueError(f"{self.asset_name}の現在価格が取得できません。")

            logger.info(f"{self.asset_name}の現在価格: ${price:.2f}")

            max_position_size = (usable_margin * self.leverage) / price
            asset_precision = 4
            max_position_size = round(max_position_size, asset_precision)

            logger.info(f"証拠金の90%での最大ポジションサイズ: {max_position_size} {self.asset_name}")
            return max_position_size
        except Exception as e:
            logger.error(f"最大ポジションサイズ計算中にエラーが発生しました: {e}")
            return 0

    def initialize_exchange(self):
        private_key = settings.hyperliquid_private_key
        account_address = settings.hyperliquid_account_address
        monitoring_address = settings.hyperliquid_monitoring_address

        if not private_key or not monitoring_address:
            logger.error("必要な環境変数が設定されていません。")
            return

        try:
            wallet: LocalAccount = Account.from_key(private_key)
            logger.info(f"ウォレットアドレス: {wallet.address}")
            self.exchange = Exchange(
                wallet=wallet,
                base_url=MAINNET_API_URL,
                vault_address=None,
                account_address=account_address
            )
            self.exchange.update_leverage(
                leverage=self.leverage,
                name=self.asset_name,
                is_cross=self.is_cross
            )
            self.max_position_size = self.calculate_max_position_size()
            if self.max_position_size > 0:
                self.exchange_initialized = True
        except Exception as e:
            logger.error(f"Exchange初期化中にエラーが発生しました: {e}")

    def open_position(self, is_buy: bool, size: float, slippage: float = 0.05):
        try:
            market_response = self.exchange.market_open(
                name=self.asset_name,
                is_buy=is_buy,
                sz=size,
                slippage=slippage,
                cloid=None,
                builder=None
            )
            if market_response.get('status') == 'ok':
                data = market_response.get('response', {}).get('data', {})
                statuses = data.get('statuses', [])
                for status_item in statuses:
                    filled_info = status_item.get('filled')
                    if filled_info:
                        entry_px = float(filled_info.get('avgPx'))
                        direction = "買い" if is_buy else "売り"
                        logger.info(f"ポジションをオープンしました。方向: {direction}, エントリープライス: ${entry_px:.2f}, サイズ: {size} {self.asset_name}")
                        return entry_px
            else:
                logger.error(f"マーケット注文に失敗しました: {market_response.get('response')}")
                return None
        except Exception as e:
            logger.error(f"ポジションのオープン中にエラーが発生しました: {e}")
            return None

    def close_position(self, size: float, entry_px: float, is_buy: bool, slippage: float = 0.05):
        close_is_buy = not is_buy
        try:
            close_response = self.exchange.market_open(
                name=self.asset_name,
                is_buy=close_is_buy,
                sz=size,
                slippage=slippage,
                cloid=None,
                builder=None
            )
            if close_response.get('status') == 'ok':
                data = close_response.get('response', {}).get('data', {})
                statuses = data.get('statuses', [])
                for status_item in statuses:
                    filled_info = status_item.get('filled')
                    if filled_info:
                        close_px = float(filled_info.get('avgPx'))
                        logger.info(f"ポジションをクローズしました。エグジットプライス: ${close_px:.2f}, サイズ: {size} {self.asset_name}")
                        return close_px
            else:
                logger.error(f"ポジション決済に失敗しました: {close_response.get('response')}")
                return None
        except Exception as e:
            logger.error(f"ポジション決済中にエラーが発生しました: {e}")
            return None

    def handle_action(self, action: str):
        with self.position_lock:
            if self.current_position == 'none':
                is_buy = action == 'buy'
                entry_px = self.open_position(is_buy, self.max_position_size)
                if entry_px:
                    self.current_position = action
                    self.current_size = self.max_position_size
                    self.current_entry_px = entry_px
            elif self.current_position != action:
                is_buy_current = self.current_position == 'buy'
                self.close_position(self.current_size, self.current_entry_px, is_buy_current)
                is_buy_new = action == 'buy'
                entry_px = self.open_position(is_buy_new, self.max_position_size)
                if entry_px:
                    self.current_position = action
                    self.current_size = self.max_position_size
                    self.current_entry_px = entry_px
