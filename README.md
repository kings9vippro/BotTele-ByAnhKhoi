# BotTele-ByAnhKhoi · GLAZE Web Control

Dashboard web quản lý tài khoản Zalo, liên kết hồ sơ Discord/Facebook bằng
OAuth chính thức và gửi thông báo tới webhook Discord được cấp quyền. Dữ liệu
quản trị và task dùng chung SQLite. Discord OAuth2 không cấp quyền gửi tin dưới
danh tính tài khoản cá nhân. Telegram bot là tùy chọn và bị tắt trong blueprint
Render hiện tại.

## Chạy trên Render

Xem `render.yaml`, `.env.example` và `gunicorn.conf.py`. Runtime dùng Python
3.11 ở chế độ web-only. Bắt buộc cấu hình `SECRET_KEY`, `ADMIN_PASS`,
`OAUTH_PUBLIC_BASE_URL` HTTPS và `OAUTH_ENCRYPTION_KEY` Fernet. Cấu hình App
ID/Secret của từng provider trong giao diện hoặc Environment. Đăng ký callback
`/oauth/callback/discord` và `/oauth/callback/facebook` trong developer portal.
Có thể bật `DISCORD_OAUTH_PKCE=1` để thêm S256; cần kiểm thử đăng nhập thật
với ứng dụng Discord của bạn trước khi bật trong production.
Nếu muốn giữ tài khoản và hàng đợi qua redeploy, cấu hình `DATABASE_PATH` và
`APP_DATA_DIR` trên ổ lưu bền vững. Blueprint hiện dùng gói Starter và gắn `/var/data`;
Render Free không bảo đảm xử lý nền liên tục hoặc lưu tệp qua redeploy.

Facebook được kết nối bằng Facebook Login/Graph API và Discord bằng OAuth2 chính thức.
Cookie trình duyệt Facebook, mật khẩu, MFA và Discord user-token không được nhận hoặc lưu.

Lệnh chạy: `gunicorn app:app --config gunicorn.conf.py`. Đặt một Gunicorn
worker; trong worker có năm luồng cho hàng đợi thông báo. Không đăng nhập
Discord bằng mật khẩu trong bot và không nhập Discord user token.

## Kiểm tra

`python scripts/verify_startup.py`

`python -m unittest discover -s tests -p 'test_*.py' -q`

`node tests/control-browser.cjs` dùng Playwright/Chromium và máy chủ kiểm thử
ở cổng 5873; không gọi Discord/Zalo thật. Cách đo hàng đợi:
`PYTHONPATH=. python scripts/benchmark_notifications.py`.

Chi tiết phần đã làm, bằng chứng và giới hạn: [V4_DELIVERY.md](V4_DELIVERY.md).
Audit ban đầu: [AUDIT_V4.md](AUDIT_V4.md).
