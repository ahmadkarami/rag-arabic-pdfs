
from fastapi import FastAPI
from services.GenerationService import GenerationService
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any, Optional


app = FastAPI(
    title="Test project for BV-tech",
    description="API for generating answers using a RAG-based chatbot, for arabic texts.",
    version="1.0.0"
)


class QAItem(BaseModel):
    qu: str
    an: str

class QuestionRequest(BaseModel):
    question: str
    fileUrl: str
    history: Optional[List[QAItem]] = None
    chatSummary: Optional[Dict[str, Any]] = None


gen_service = GenerationService()

@app.post("/generate-answer", summary="Generate answer", description="Returns a message for users' question.")
def generate_answer(payload: QuestionRequest):
    print("---------------->>>>>>> time:", datetime.now())
    print('Start sending request')
    input_token, output_token, total_token, answer, chatSummary= gen_service.generate_answer(payload.question, payload.fileUrl, payload.history, payload.chatSummary)
    return { 
            "answer": answer,
            "inputToken": input_token,
            "outputToken": output_token,
            "totalToken": total_token,
            "chatSummary": chatSummary
        }