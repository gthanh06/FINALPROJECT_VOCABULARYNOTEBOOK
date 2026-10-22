# Vocabulary Notebook (EN–VN)

Sổ tay từ vựng Anh–Việt: lưu từ, nghĩa, loại từ, câu ví dụ và ghi chú cách dùng; ôn tập và ghi lại kết quả nhớ/quên. AI phía server gợi ý câu ví dụ và ghi chú cách dùng cho từ mới.

## Stack

- Backend: Python / FastAPI
- Database: PostgreSQL (Supabase ở production, container Postgres khi chạy local)
- Deploy: Render (HTTPS)
- CI/CD: GitHub Actions
- AI: Gemini API (dự phòng Groq)

## Chạy local (Docker)

Cần Docker Desktop. Một lệnh dựng cả app và PostgreSQL:

```bash
docker compose up --build
```

Mở http://localhost:8000. Migration tự chạy khi container app khởi động.

| Trang | Đường dẫn |
|---|---|
| Danh sách, tìm kiếm, xoá | `/#/` |
| Thêm từ | `/#/new` |
| Sửa từ | `/#/edit/{id}` |
| Ôn tập (thẻ nhớ) | `/#/review` |
| API docs | `/docs` |

Dừng: `docker compose down` (giữ dữ liệu) hoặc `docker compose down -v` (xoá luôn dữ liệu).

## Chạy test

```bash
pip install -r requirements-dev.txt
ruff check . && pytest
```

Test không cần database (dùng repository giả trong `tests/fake_repo.py`).

## Deploy lên Render

Render build từ `Dockerfile` và cấp HTTPS (`https://<tên-service>.onrender.com`) tự động.

1. Render Dashboard → **New → Blueprint** → chọn repo này. Render đọc `render.yaml` và tạo web service `vocab-notebook` (Docker, free, Singapore, health check `/health`).
2. Khi được hỏi, nhập biến môi trường bí mật:
   - `DATABASE_URL`: connection string của Supabase (Project Settings → Database → Connection string, chế độ *Transaction pooler*, cổng 6543). Thêm `?sslmode=require` ở cuối nếu chưa có.
3. `APP_ENV=production` đã khai báo sẵn trong `render.yaml`.
4. Mỗi lần merge vào `main`, Render tự build và deploy lại. Container chạy `python -m app.migrate` trước khi khởi động nên schema luôn được cập nhật.

Kiểm tra sau deploy: `/health` → `{"status":"ok"}`, `/health/db` → `{"db":"ok", ...}`, `/api/info` → `"env": "production"`.

Biến môi trường:

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | có | Chuỗi kết nối PostgreSQL |
| `APP_ENV` | không | `development` / `production`, hiện ở `/api/info` |
| `PORT` | không | Render tự đặt; mặc định 8000 |

## Quy tắc làm việc

- Không commit thẳng vào `main`: mọi thay đổi đi qua pull request và phải có người khác review.
- Không commit `.env`, key hay connection string. Cấu hình đọc từ biến môi trường.
