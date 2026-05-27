# Hướng dẫn xây dựng API `/guided`

API `/guided` nhận `doc_id` từ người dùng, lấy nội dung tài liệu đã upload, rồi dùng AI tóm tắt thành **5 mục chính** có cấu trúc.

---

## 1. Luồng xử lý tổng quan

```
POST /docs/{doc_id}/guided
        │
        ▼
[1] Xác thực user (X-User-Id header)
        │
        ▼
[2] Tìm doc trong userstore → lấy filename
        │
        ▼
[3] Đọc nội dung file từ storage → extract text
        │
        ▼
[4] Gửi text + prompt tóm tắt 5 mục → AI (invoke)
        │
        ▼
[5] Parse kết quả → trả về JSON có 5 sections
```

---

## 2. Request / Response

**Request**
```
POST /docs/{doc_id}/guided
Header: X-User-Id: <user_id>          (tuỳ chọn, fallback về default_user_id)
```

**Response thành công**
```json
{
  "doc_id": "abc-123",
  "filename": "lecture.pdf",
  "summary": {
    "section_1": { "title": "...", "content": "..." },
    "section_2": { "title": "...", "content": "..." },
    "section_3": { "title": "...", "content": "..." },
    "section_4": { "title": "...", "content": "..." },
    "section_5": { "title": "...", "content": "..." }
  }
}
```

---

## 3. Prompt gửi cho AI

Prompt cần yêu cầu AI trả về JSON có cấu trúc cố định để dễ parse:

```python
GUIDED_PROMPT = """You are a study assistant. Read the document below and produce a structured summary with EXACTLY 5 key sections.

Return ONLY valid JSON in this exact format:
{{
  "section_1": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_2": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_3": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_4": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_5": {{"title": "<short title>", "content": "<2-3 sentence summary>"}}
}}

DOCUMENT:
{text}
"""
```

> Dùng `{{` / `}}` để escape dấu ngoặc nhọn trong f-string Python.

---

## 4. Các bước cài đặt

### 4.1 Thêm handler vào `src/handlers.py`

```python
def handle_guided_summary(
    user_id: str,
    doc_id: str,
    storage,
    userstore,
    ai_client,
) -> dict:
    import json

    # Bước 1: Tìm tài liệu
    docs = userstore.list_docs(user_id)
    doc = next((d for d in docs if d["doc_id"] == doc_id), None)
    if not doc:
        raise ValueError(f"Document {doc_id} not found for user {user_id}")

    filename = doc.get("filename", "unknown")

    # Bước 2: Lấy nội dung từ storage
    key = f"{user_id}/{doc_id}/{filename}"
    data = storage.get(key)
    text = _extract_text(filename, data)

    if not text.strip():
        raise ValueError("Document has no extractable text")

    # Bước 3: Giới hạn độ dài để tránh vượt context window
    max_chars = 12000
    truncated_text = text[:max_chars]

    # Bước 4: Gọi AI
    prompt = GUIDED_PROMPT.format(text=truncated_text)
    raw = ai_client.invoke(prompt, max_tokens=1024)

    # Bước 5: Parse JSON từ response
    try:
        # Trích xuất JSON nếu AI trả về text thừa xung quanh
        start = raw.index("{")
        end = raw.rindex("}") + 1
        summary = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        # Fallback: trả về raw text trong section_1
        summary = {
            "section_1": {"title": "Summary", "content": raw},
            "section_2": {"title": "", "content": ""},
            "section_3": {"title": "", "content": ""},
            "section_4": {"title": "", "content": ""},
            "section_5": {"title": "", "content": ""},
        }

    return {
        "doc_id": doc_id,
        "filename": filename,
        "summary": summary,
    }
```

Cũng thêm `GUIDED_PROMPT` constant vào đầu file `handlers.py`:

```python
GUIDED_PROMPT = """You are a study assistant. Read the document below and produce a structured summary with EXACTLY 5 key sections.

Return ONLY valid JSON in this exact format:
{{
  "section_1": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_2": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_3": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_4": {{"title": "<short title>", "content": "<2-3 sentence summary>"}},
  "section_5": {{"title": "<short title>", "content": "<2-3 sentence summary>"}}
}}

DOCUMENT:
{text}
"""
```

### 4.2 Thêm route vào `src/app.py`

```python
@app.post("/docs/{doc_id}/guided")
def guided_summary(doc_id: str, x_user_id: str | None = Header(default=None)) -> dict:
    user_id = _resolve_user_id(x_user_id)
    try:
        return handlers.handle_guided_summary(
            user_id=user_id,
            doc_id=doc_id,
            storage=storage,
            userstore=userstore,
            ai_client=ai_client,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 5. Lưu ý quan trọng

| Vấn đề | Giải pháp |
|---|---|
| Tài liệu quá dài | Truncate text về ~12.000 ký tự trước khi gửi AI |
| AI không trả về JSON hợp lệ | Dùng `try/except` + fallback như trên |
| Tài liệu không tồn tại | Raise `ValueError` → HTTP 404 |
| LocalAI stub | Trả về chuỗi giả, parse sẽ vào fallback — hoạt động bình thường khi dev local |

---

## 6. Test nhanh

Sau khi upload một tài liệu và lấy `doc_id`:

```bash
curl -X POST http://localhost:8000/docs/<doc_id>/guided \
  -H "X-User-Id: test-user-001"
```
