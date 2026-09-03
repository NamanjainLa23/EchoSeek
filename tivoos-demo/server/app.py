from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.routers.generate import router as gen_router
from server.routers.recap import router as recap_router
# from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parent / ".env")

app = FastAPI(title="TiVoOS Server (Bedrock)")

# Allow your React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.mount("/static", StaticFiles(directory="server/static"), name="static")

app.include_router(gen_router)
app.include_router(recap_router)

@app.get("/")
def root():
    return {"ok": True}
