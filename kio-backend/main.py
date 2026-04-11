from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from ai.rag import qa_chain

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    query: str

@app.get("/")
def root():
    return {"msg": "hello"}

@app.post("/api/question")
async def ask_menu(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")
    
    answer = qa_chain.invoke(request.query)
    return {"question": request.query, "answer": answer}