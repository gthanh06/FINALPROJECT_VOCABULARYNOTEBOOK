# Vocabulary Notebook (EN–VN)

Sổ tay từ vựng Anh–Việt: lưu từ, nghĩa, loại từ, câu ví dụ và ghi chú cách dùng; ôn tập và ghi lại kết quả nhớ/quên. AI phía server gợi ý câu ví dụ và ghi chú cách dùng cho từ mới.

## Stack

- Backend: Python / FastAPI
- Database: PostgreSQL (Supabase ở production, container Postgres khi chạy local)
- Deploy: Render (HTTPS)
- CI/CD: GitHub Actions
- AI: Gemini API (gợi ý phía server)

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

## Thêm nhiều từ: Import / Export CSV (admin)

- Trang Admin có **Import CSV**: chọn file → web kiểm tra và hiện bản xem trước (bao nhiêu từ mới, bao nhiêu từ đã có, dòng nào lỗi) → bấm **Import** mới lưu. File còn dòng lỗi thì không lưu được. Tuỳ chọn ghi đè từ đã có.
- **Export CSV** tải toàn bộ kho từ cùng định dạng, mở được bằng Excel (UTF-8), sửa xong import lại.
- Định dạng: `word,meaning_vi,part_of_speech,example,usage_note,topic` (chỉ `word` và `meaning_vi` bắt buộc); file mẫu ở `/static/words-template.csv`. API: `POST /api/admin/import` (`dry_run` = chỉ kiểm tra), `GET /api/admin/words.csv`.
- **1000 từ có sẵn**: `data/ngsl_1000.csv`, dựng từ NGSL + Wiktionary tiếng Việt + Tatoeba bằng `scripts/build_wordlist.py`, nghĩa đã được soát lại; `scripts/ai_enrich.py` dùng Gemini để điền ô trống hoặc gợi ý từ mới theo chủ đề. Nguồn, giấy phép và cách làm: [data/README.md](data/README.md).

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
| Quiz từ sổ tay (trắc nghiệm, điền từ, chọn nghĩa) | `/#/quiz` |
| Ôn cách quãng SM-2, các từ đến hạn hôm nay | `/#/srs` |
| API docs | `/docs` |

Quiz tạo từ các từ trong sổ riêng, lưu đáp án trên server và chỉ trả lời đúng sau khi nộp bài. Ôn cách quãng cũng dùng sổ riêng: tự đánh giá mức nhớ 0–5, server cập nhật ease factor, khoảng cách và ngày ôn kế tiếp theo giờ Việt Nam. Khi chọn mức 0–2, ứng dụng xin AI tạo mẹo ghi nhớ; kết quả được cache dùng lại. Các API nằm dưới `/api/quiz` và `/api/srs`.

Dừng: `docker compose down` (giữ dữ liệu) hoặc `docker compose down -v` (xoá luôn dữ liệu).

## Chạy test

```bash
pip install -r requirements-dev.txt
ruff check . && pytest
```

Test không cần database (dùng repository giả trong `tests/fake_repo.py`).

## CI/CD, AI và bảo mật

- Pull request chạy Ruff, pytest, Docker build và Gitleaks trên toàn bộ lịch sử Git (`fetch-depth: 0`). Không merge nếu một job thất bại.
- Sau khi các job trên thành công khi push/merge vào `main`, GitHub Actions gọi Render Deploy Hook nếu repository có secret `RENDER_DEPLOY_HOOK_URL` (Settings → Secrets and variables → Actions; URL lấy ở Render → service → Settings → Deploy Hook). Chưa có secret thì bước deploy được bỏ qua và Render vẫn tự deploy (`autoDeploy: true`). Chỉ đổi `autoDeploy: false` trong `render.yaml` **sau khi** đã thêm secret, để không deploy hai lần.
- Bật branch protection cho `main` trong GitHub → Settings → Branches → Add branch protection rule: yêu cầu pull request, ít nhất 1 approval, và các status check `Scan Git history` cùng `Lint, test, and build`; chặn force-push và xoá nhánh. Các quy tắc này cần được bật trong cài đặt GitHub của repository.
- Tạo `.env` từ [.env.example](.env.example) khi chạy local. `GEMINI_API_KEY` chỉ nằm ở server. Toàn bộ phần AI nằm trong `app/ai/`, prompt trong `prompts/`. Endpoint: `POST /api/ai/lookup` (nút **✨ AI điền** khi thêm từ) và `POST /api/ai/check-sentence` (trang **Sổ của tôi → ✍️ Đặt câu**: AI chấm câu tự đặt với một từ trong sổ, giải thích lỗi bằng tiếng Việt, đưa câu đã sửa). Mọi endpoint AI yêu cầu đăng nhập, giới hạn lượt mỗi người, cache kết quả, thử lại khi gặp lỗi 429.

## Deploy lên Render

Render build từ `Dockerfile` và cấp HTTPS (`https://<tên-service>.onrender.com`).

1. Render Dashboard → **New → Blueprint** → chọn repo này. Render đọc `render.yaml` và tạo web service `vocab-notebook` (Docker, free, Singapore, health check `/health`).
2. Khi được hỏi, nhập biến môi trường bí mật:
   - `DATABASE_URL`: connection string của Supabase (Project Settings → Database → Connection string, chế độ *Transaction pooler*, cổng 6543). Thêm `?sslmode=require` ở cuối nếu chưa có.
   - `ADMIN_EMAIL` và `ADMIN_PASSWORD`: tài khoản admin.
   - `GEMINI_API_KEY`: API key Gemini để bật gợi ý AI.
3. `APP_ENV=production` và `GEMINI_MODEL` đã khai báo sẵn trong `render.yaml`.
4. Mỗi lần merge vào `main`, Render tự build và deploy lại (hoặc qua Deploy Hook, xem phần CI/CD ở trên). Container chạy `python -m app.migrate` trước khi khởi động nên schema luôn được cập nhật.

Kiểm tra sau deploy: `/health` → `{"status":"ok"}`, `/health/db` → `{"db":"ok", ...}`, `/api/info` → `"env": "production"`.

Biến môi trường:

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `DATABASE_URL` | có | Chuỗi kết nối PostgreSQL |
| `APP_ENV` | không | `development` / `production`, hiện ở `/api/info`; `production` bật cookie `Secure` |
| `PORT` | không | Render tự đặt; mặc định 8000 |
| `ADMIN_EMAIL` | không | Email tài khoản admin, tạo / nâng quyền khi khởi động |
| `ADMIN_PASSWORD` | không | Mật khẩu admin (≥ 8 ký tự); là secret, không commit |
| `GEMINI_API_KEY` | không | API key Gemini; cần để dùng gợi ý AI, không commit |
| `GEMINI_MODEL` | không | Mô hình Gemini; mặc định `gemini-3.5-flash-lite` |

## Quy tắc làm việc

- Không commit thẳng vào `main`: mọi thay đổi đi qua pull request và phải có người khác review.
- Không commit `.env`, key hay connection string. Cấu hình đọc từ biến môi trường.
