# BotTele-ByAnhKhoi · GLAZE Web Control

Bảng điều khiển web quản lý tài khoản và tác vụ Zalo, Discord, Facebook. Đăng
nhập quản trị bằng mật khẩu web hoặc phiên Telegram đã cấp quyền. Liên kết
Discord bằng token và Facebook bằng cookie được kiểm tra với nhà cung cấp;
thông tin nhạy cảm được mã hóa khi lưu. Giao diện không hiển thị lại token hoặc
cookie đã lưu.

## Chạy trên Render

`render.yaml` hiện chạy Gunicorn/Python. Đặt `SECRET_KEY` và `ADMIN_PASS` trong
Environment, không commit giá trị thật vào Git. Nếu cần giữ dữ liệu qua lần
triển khai, đặt `APP_DATA_DIR` và `DATABASE_PATH` trên đĩa bền vững. Render Free
có thể ngủ và ổ lưu tạm sẽ mất dữ liệu sau khi tạo lại instance. Đường kiểm tra
sức khỏe là `/healthz`.

Đường đăng nhập OAuth Discord/Zalo cũ đã được gỡ khỏi giao diện và trả về 410.
Màn hình kết nối tài khoản dùng token Discord, cookie Facebook, cookie và IMEI
Zalo. Mã QR Zalo có thể tải tệp phiên về thiết bị sau khi xác thực thành công.

## Lớp web Rust thử nghiệm

`rust-gateway/` dùng Axum để phục vụ HTML, CSS, JavaScript và chuyển tiếp API
đến Python. Nó giữ luồng tác vụ và dữ liệu hiện tại trong Python; chưa phải bản
chuyển toàn bộ ứng dụng sang Rust. Cổng `/healthz` chỉ báo thành công khi
backend Python cũng trả về trạng thái khỏe.

Chạy thử tại thư mục gốc của repo, sau khi cài Rust 1.100 trở lên và các
dependency Python:

```sh
PORT=5001 BIND_HOST=127.0.0.1 gunicorn app:app --config gunicorn.conf.py
# Trong terminal khác:
cargo build --release --locked --manifest-path rust-gateway/Cargo.toml
PORT=5000 YANBI_ROOT=. YANBI_PYTHON_UPSTREAM=http://127.0.0.1:5001 \
  rust-gateway/target/release/yanbi-gateway
```

Cấu hình xác thực và dữ liệu cho tiến trình Python theo `.env.example`. Chưa
chuyển `render.yaml` sang Rust khi chưa kiểm tra được dịch vụ Render đang phục
vụ trang thực tế.

## Kiểm tra

```sh
python scripts/verify_startup.py
python -m unittest discover -s tests -p 'test_*.py' -q
cargo test --locked --manifest-path rust-gateway/Cargo.toml
```

`node tests/control-browser.cjs` cần Playwright/Chromium và máy chủ thử nghiệm
ở cổng 5873. Đặt `WEB_TEST_BASE_URL` để chạy cùng bài thử qua cổng Rust.
