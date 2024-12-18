# app/main.py
import uvicorn
from fastapi import FastAPI
from .webhook import router as webhook_router
from .logger import logger

def create_app():
    app = FastAPI()
    app.include_router(webhook_router)
    return app

app = create_app()

def main():
    logger.info("Webhookサーバーを起動します。")
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)

if __name__ == "__main__":
    main()
