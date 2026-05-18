from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.ocr.router import router as ocr_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr_router)


@app.get("/")
def root():
    return {"msg": "hello"}
