from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(title="Scheduling App API", version="1.0.0")

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": str(exc), "details": {}},
    )


from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.bid_periods import router as bid_periods_router
from app.routes.sequences import router as sequences_router
from app.routes.bids import router as bids_router
from app.routes.bookmarks import router as bookmarks_router
from app.routes.filter_presets import router as filter_presets_router
from app.routes.awarded_schedules import router as awarded_schedules_router
from app.routes.awards import router as awards_router
from app.routes.guided import router as guided_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(bid_periods_router)
app.include_router(sequences_router)
app.include_router(bids_router)
app.include_router(bookmarks_router)
app.include_router(filter_presets_router)
app.include_router(awarded_schedules_router)
app.include_router(awards_router)
app.include_router(guided_router)


@app.get("/")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/airlines")
async def list_airlines():
    from app.services.airline_configs import list_airline_configs
    return {"data": list_airline_configs()}
