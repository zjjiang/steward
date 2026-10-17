"""web 仪表盘入口：`uv run uvicorn app.web.server:app --host 127.0.0.1`。

只读观察窗，只绑回环地址；lifespan 退出时关闭本进程的 FinanceBackend 子进程。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.finance.backend import close_backend
from app.web.routes import router

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def _lifespan(server: FastAPI):
    try:
        yield
    finally:
        await close_backend()


app = FastAPI(title="steward 仪表盘", lifespan=_lifespan)
app.include_router(router)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(_STATIC_DIR / "index.html")
