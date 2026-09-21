# -*- coding: utf-8 -*-
"""启动入口：uvicorn + 内置调度器"""
import uvicorn
from app import config
from app.main import app
from app import sync

if __name__ == "__main__":
    scheduler = sync.run_scheduler()
    try:
        uvicorn.run(app, host=config.API_HOST, port=config.API_PORT,
                    log_level="info", access_log=False)
    finally:
        scheduler.shutdown()
