"""문서를 문단으로 나누고, 질문 단어가 많이 들어 있는 문단을 찾습니다."""


def load_chunks(documents):
    chunks = []
    for document in documents:
        # 윈도우에서 만든 TXT는 줄바꿈이 \r\n 이라 먼저 \n 으로 맞춥니다.
        content = document["content"].replace("\r\n", "\n")
        # TXT 한 개의 내용을 빈 줄 기준으로 나눕니다.
        for paragraph in content.split("\n\n"):
            paragraph = paragraph.strip()
            if paragraph:
                chunks.append(
                    {"source": document["filename"], "text": paragraph}
                )
    return chunks


def make_words(text):
    cleaned = text.lower()
    for mark in "?!,./:()-_'\"":
        cleaned = cleaned.replace(mark, " ")
    return cleaned.split()


def word_forms(word):
    # "명령어를", "커밋은"처럼 조사가 붙은 단어도 찾을 수 있게
    # 끝 글자를 1~2개 뗀 형태도 같이 검색합니다.
    forms = [word]
    for cut in (1, 2):
        if len(word) - cut >= 2:
            forms.append(word[:-cut])
    return forms


def contains(word, text):
    for form in word_forms(word):
        if form in text:
            return True
    return False


def score_chunk(question_words, chunk):
    text = chunk["text"].lower()
    filename = " ".join(make_words(chunk["source"]))
    score = 0
    for word in question_words:
        # 문단 안에 질문 단어가 있으면 2점,
        # 파일 이름에도 있으면 그 파일의 문단에 3점을 더 줍니다.
        if contains(word, text):
            score += 2
        if contains(word, filename):
            score += 3
    return score


def find_chunks(question, documents, limit=3):
    question_words = [word for word in make_words(question) if len(word) > 1]
    scored = []

    for chunk in load_chunks(documents):
        score = score_chunk(question_words, chunk)
        if score > 0:
            scored.append({"score": score, "chunk": chunk})

    # 점수가 높은 문단부터 limit개를 고릅니다.
    scored.sort(key=lambda item: item["score"], reverse=True)
    return [item["chunk"] for item in scored[:limit]]
