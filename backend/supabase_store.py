"""Supabase(llm 스키마)에 문서와 채팅을 저장하고 읽습니다.

모든 요청은 로그인한 사용자의 토큰으로 보냅니다.
그래서 Supabase의 RLS 정책이 "자기 데이터만" 읽고 쓰게 막아 줍니다.
"""

import os

import httpx
from fastapi import HTTPException


def settings():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not url or not key:
        raise HTTPException(500, "Supabase 환경 변수가 없습니다.")
    return url, key


def rest(method, table, token, params=None, body=None):
    url, key = settings()
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + token,
        "Accept-Profile": "llm",
        "Content-Profile": "llm",
    }
    if body is not None:
        # 저장한 행을 응답으로 돌려받습니다.
        headers["Prefer"] = "return=representation"
    try:
        response = httpx.request(
            method,
            url + "/rest/v1/" + table,
            headers=headers,
            params=params,
            json=body,
            timeout=15,
        )
    except httpx.RequestError:
        raise HTTPException(502, "Supabase 연결에 실패했습니다.")
    if response.status_code == 409:
        raise HTTPException(409, "같은 이름의 문서가 있습니다.")
    if response.status_code >= 400:
        raise HTTPException(502, "Supabase 요청 실패: " + response.text[:200])
    return response.json() if response.content else []


# ---------- 문서 ----------

def list_documents(token):
    return rest("GET", "documents", token, {
        "select": "id,filename,created_at",
        "order": "created_at.desc",
    })


def all_document_texts(token):
    return rest("GET", "documents", token, {"select": "filename,content"})


def add_document(token, user_id, filename, content):
    rows = rest("POST", "documents", token, body={
        "user_id": user_id,
        "filename": filename,
        "content": content,
    })
    return rows[0]["id"]


# ---------- 채팅 ----------

def list_chat_sessions(token):
    return rest("GET", "chat_sessions", token, {
        "select": "id,title,created_at",
        "order": "created_at.desc",
    })


def create_chat_session(token, user_id, title):
    rows = rest("POST", "chat_sessions", token, body={
        "user_id": user_id,
        "title": title,
    })
    return rows[0]


def chat_session_exists(token, session_id):
    rows = rest("GET", "chat_sessions", token, {
        "select": "id",
        "id": "eq." + session_id,
    })
    return bool(rows)


def list_turns(token, session_id):
    return rest("GET", "chat_turns", token, {
        "select": "id,question,answer,sources,created_at",
        "session_id": "eq." + session_id,
        "order": "created_at.asc",
    })


def add_turn(token, user_id, session_id, question, answer, sources):
    rows = rest("POST", "chat_turns", token, body={
        "user_id": user_id,
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "sources": sources,
    })
    return rows[0]
