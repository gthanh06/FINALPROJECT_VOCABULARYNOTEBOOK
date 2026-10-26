# Vocabulary Notebook (EN–VN)

Sổ tay từ vựng Anh–Việt: lưu từ, nghĩa, loại từ, câu ví dụ và ghi chú cách dùng; ôn tập và ghi lại kết quả nhớ/quên. AI phía server gợi ý câu ví dụ và ghi chú cách dùng cho từ mới.

## Stack

- Backend: Python / FastAPI
- Database: PostgreSQL (Supabase ở production, container Postgres khi chạy local)
- Deploy: Render (HTTPS)
- CI/CD: GitHub Actions
- AI: Gemini API (dự phòng Groq)

## Tài khoản, vai trò & đăng nhập

- Hai vai trò (`users.role`):
  - **learner** (mặc định khi đăng ký): xem từ theo chủ đề, ôn tập, xem tiến độ của chính mình ở trang `#/progress`; lịch sử ôn tập là của riêng mỗi người.
  - **admin**: thêm / sửa / xoá từ trong **kho từ chung** mà mọi learner cùng học, xem tiến độ learner ở trang `#/admin`. API thêm/sửa/xoá từ trả `403` nếu không phải admin.
- **Không ai tự đăng ký được admin**: đăng ký luôn tạo learner. Trang đăng nhập có ô nhỏ **Admin** mở form đăng nhập riêng (`#/admin-login`); server từ chối (`403`, không tạo session) mọi tài khoản không phải admin đăng nhập ở đó.
- **Tạo tài khoản admin**: đặt `ADMIN_EMAIL` và `ADMIN_PASSWORD` (≥ 8 ký tự). Mỗi lần container khởi động, `python -m app.migrate` tạo tài khoản đó với vai trò admin, hoặc nâng tài khoản đã có email đó lên admin và đặt lại mật khẩu theo `ADMIN_PASSWORD`.
  - Render: Dashboard → service → **Environment** → thêm 2 biến, rồi deploy lại.
  - Local: tạo file `.env` (đã có trong `.gitignore`) chứa 2 dòng `ADMIN_EMAIL=...` và `ADMIN_PASSWORD=...`, rồi `docker compose up --build`.
- Mật khẩu băm bằng `scrypt` (salt ngẫu nhiên, `app/security.py`); DB không lưu mật khẩu gốc.
- Đăng nhập tạo session: trình duyệt giữ token ngẫu nhiên trong cookie `HttpOnly`, `SameSite=Lax` (`Secure` khi `APP_ENV=production`); DB chỉ lưu SHA-256 của token, hết hạn sau 30 ngày. Đăng xuất xoá session trên server.
- API: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET /api/me/progress`, `GET /api/admin/users` (admin). Mọi route `/api/...` trả `401` nếu chưa đăng nhập.

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
| `APP_ENV` | không | `development` / `production`, hiện ở `/api/info`; `production` bật cookie `Secure` |
| `PORT` | không | Render tự đặt; mặc định 8000 |
| `ADMIN_EMAIL` | không | Email tài khoản admin, tạo / nâng quyền khi khởi động |
| `ADMIN_PASSWORD` | không | Mật khẩu admin (≥ 8 ký tự); là secret, không commit |

## Quy tắc làm việc

- Không commit thẳng vào `main`: mọi thay đổi đi qua pull request và phải có người khác review.
- Không commit `.env`, key hay connection string. Cấu hình đọc từ biến môi trường.
