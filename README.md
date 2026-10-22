# Vocabulary Notebook (EN–VN)

Sổ tay từ vựng Anh–Việt: lưu từ, nghĩa, loại từ, câu ví dụ và ghi chú cách dùng; ôn tập và ghi lại kết quả nhớ/quên. AI phía server gợi ý câu ví dụ và ghi chú cách dùng cho từ mới.

## Stack

- Backend: Python / FastAPI
- Database: PostgreSQL (Supabase ở production, container Postgres khi chạy local)
- Deploy: Render (HTTPS)
- CI/CD: GitHub Actions
- AI: Gemini API (dự phòng Groq)

## Quy tắc làm việc

- Không commit thẳng vào `main`: mọi thay đổi đi qua pull request và phải có người khác review.
- Không commit `.env`, key hay connection string. Cấu hình đọc từ biến môi trường.
