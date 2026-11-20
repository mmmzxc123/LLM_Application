"""승인된 사용자만 쓰는 문서 질문 챗봇 API.

문서와 대화는 Supabase(llm 스키마)에 사용자별로 저장합니다.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, UploadFile
from google import genai
from pydantic import BaseModel, Field

from auth_guard import require_approved
from retrieval import find_chunks
import supabase_store as store


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")
MAX_FILE_SIZE = 1_000_000  # 수업에서는 TXT 파일을 1 MB까지만 받습니다.


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=500)


class NewSessionRequest(BaseModel):
    title: str = Field(default="새 채팅", max_length=60)


# ---------- 문서 ----------

@app.get("/api/documents")
def get_documents(authorization: str = Header(default="")):
    token, _ = require_approved(authorization)
    # 브라우저 왼쪽 목록에는 문서 내용 대신 이름과 ID만 보냅니다.
    return {"documents": store.list_documents(token)}


@app.post("/api/documents")
def upload_document(file: UploadFile, authorization: str = Header(default="")):
    token, user_id = require_approved(authorization)

    # 브라우저가 보낸 파일명에서 폴더 경로를 제거합니다.
    filename = (file.filename or "").replace("\\", "/").split("/")[-1]
    if not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="TXT 파일만 올릴 수 있습니다.")

    # 크기를 제한하고 UTF-8 텍스트인지 확인합니다.
    data = file.file.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="파일은 1 MB 이하여야 합니다.")
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="UTF-8 TXT 파일을 선택하세요.")
    if not content.strip():
        raise HTTPException(status_code=400, detail="내용이 비어 있습니다.")

    document_id = store.add_document(token, user_id, filename, content)
    return {"id": document_id, "filename": filename}


# ---------- 채팅방 ----------

@app.get("/api/chat-sessions")
def get_chat_sessions(authorization: str = Header(default="")):
    token, _ = require_approved(authorization)
    return {"sessions": store.list_chat_sessions(token)}


@app.post("/api/chat-sessions")
def new_chat_session(request: NewSessionRequest,
                     authorization: str = Header(default="")):
    token, user_id = require_approved(authorization)
    title = request.title.strip() or "새 채팅"
    return {"session": store.create_chat_session(token, user_id, title)}


@app.get("/api/chat-sessions/{session_id}/turns")
def get_turns(session_id: str, authorization: str = Header(default="")):
    token, _ = require_approved(authorization)
    if not store.chat_session_exists(token, session_id):
        raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다.")
    return {"turns": store.list_turns(token, session_id)}


# ---------- 질문 ----------

@app.post("/api/chat")
def chat(request: ChatRequest, authorization: str = Header(default="")):
    token, user_id = require_approved(authorization)
    if not store.chat_session_exists(token, request.session_id):
        raise HTTPException(status_code=404, detail="채팅을 찾을 수 없습니다.")

    documents = store.all_document_texts(token)
    chunks = find_chunks(request.question, documents)

    if not chunks:
        answer = "자료에서 관련 내용을 찾지 못했습니다."
        sources = []
    else:
        context = ""
        for chunk in chunks:
            context += "파일: " + chunk["source"] + "\n"
            context += chunk["text"] + "\n\n"

        prompt = "아래 발췌문을 근거로 질문에 답하세요.\n"
        prompt += "발췌문에 답이 없으면 근거가 부족하다고 말하세요.\n\n"
        prompt += "발췌문:\n" + context
        prompt += "질문: " + request.question

        client = genai.Client()
        interaction = client.interactions.create(
            model="gemini-3.5-flash-lite", input=prompt
        )
        answer = interaction.output_text

        sources = []
        for chunk in chunks:
            if chunk["source"] not in sources:
                sources.append(chunk["source"])

    # 질문과 답변 한 쌍을 DB에 저장하고, 저장된 행을 화면에 돌려줍니다.
    turn = store.add_turn(
        token, user_id, request.session_id, request.question, answer, sources
    )
    return {"turn": turn}
