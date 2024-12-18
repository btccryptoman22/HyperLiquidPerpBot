# app/webhook.py
import re
from fastapi import APIRouter, Request, HTTPException
from .exchange_manager import ExchangeManager
from .logger import logger

router = APIRouter()

# 正規表現パターンをモジュールレベルで定義
WEBHOOK_PATTERN = r':\s+([\w\d]+)\s+で\s+(BUY|SELL|buy|sell)\s+@\s+([\d.]+)\s+の注文が約定しました。新しいストラテジーポジションは\s+[-\d.]+\s+です'

class WebhookHandler:
    def __init__(self, exchange_manager: ExchangeManager):
        self.exchange_manager = exchange_manager

    async def handle_webhook(self, request: Request):
        if not self.exchange_manager.exchange_initialized:
            logger.error("Exchange not initialized.")
            raise HTTPException(status_code=500, detail="Exchange not initialized.")

        try:
            raw_body = await request.body()
            message = raw_body.decode('utf-8').strip()
            if not message:
                logger.error("Empty message received.")
                raise HTTPException(status_code=400, detail="Empty message.")

            match = re.search(WEBHOOK_PATTERN, message)
            if not match:
                logger.error(f"Webhookメッセージの解析に失敗しました: {message}")
                raise HTTPException(status_code=400, detail="Invalid message format.")

            ticker, action, _ = match.groups()
            action = action.lower()

            logger.info(f"Webhook受信 - Ticker: {ticker}, Action: {action}")
            self.exchange_manager.handle_action(action)
            return {"status": "success"}

        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Webhook処理中にエラーが発生しました: {e}")
            raise HTTPException(status_code=500, detail="Internal server error.")

webhook_handler = WebhookHandler(ExchangeManager())

@router.get("/")
async def root():
    return {"message": "Webhookサーバーが正常に稼働しています。"}

@router.post("/webhook")
async def webhook_endpoint(request: Request):
    return await webhook_handler.handle_webhook(request)
