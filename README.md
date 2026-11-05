# BotTele-ByAnhKhoi · GLAZE v2.0

Telegram bot quản lý tài khoản Zalo, liên kết hồ sơ Discord qua OAuth2 và gửi
thông báo tới webhook Discord được cấp quyền. Mini App là giao diện quản lý
trên cùng nguồn dữ liệu SQLite. Discord OAuth2 không cấp quyền gửi tin dưới
danh tính tài khoản cá nhân.

## Chạy trên Render

Xem `render.yaml` và `gunicorn.conf.py`. Runtime dùng Python 3.11. Cấu hình
biến môi trường `TELEGRAM_BOT_TOKEN` (token **mới** đã xoay),
`TELEGRAM_ADMIN_ID`, `SECRET_KEY` cố định, `OAUTH_PUBLIC_BASE_URL` HTTPS,
`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `OAUTH_ENCRYPTION_KEY` Fernet.
Đăng ký callback `/oauth/callback/discord` trong Discord Developer Portal.
Có thể bật `DISCORD_OAUTH_PKCE=1` để thêm S256; cần kiểm thử đăng nhập thật
với ứng dụng Discord của bạn trước khi bật trong production.
Nếu muốn giữ tài khoản và hàng đợi qua redeploy, cấu hình `DATABASE_PATH` và
`APP_DATA_DIR` trên ổ lưu bền vững. Render Free mặc định không bảo đảm điều đó.

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
