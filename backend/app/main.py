from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import games, v1

app = FastAPI(title="Indie Game PMF Analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games.router)
app.include_router(v1.router)


@app.get("/")
async def root():
    return {"message": "Indie Game PMF Analyzer API", "docs": "/docs"}
