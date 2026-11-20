from document_store import all_document_texts
from retrieval import load_chunks

chunks = load_chunks(all_document_texts())
print("문단 수:", len(chunks))

for chunk in chunks[:3]:
    #print(chunk["source"], chunk["text"][:60])
    print(f"파일명 : {chunk['source']}")
    print(f"내용 : {chunk['text'][:60]}\n")
