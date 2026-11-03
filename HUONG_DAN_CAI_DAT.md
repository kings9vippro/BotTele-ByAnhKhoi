# HƯỚNG DẪN DỰ ÁN GLAZE
Nhà Phát Triển: Dev Khôi Phan & Dev Anh Khôi
Phiên Bản: v1.1.0

## 1. Cấu trúc dự án

- `app.py`: Máy chủ Flask, kết nối và xử lý tác vụ.
- `zalo_core.cpp`: Mã nguồn C++ lưu tham khảo; ứng dụng hiện không nạp tệp nhị phân dựng sẵn.
- `get_ck_im_zalo.py`: Bộ điều khiển Telegram.
- `zalo_login.py`: Đăng nhập QR và quản lý phiên Zalo.
- `templates/miniapp.html`: Giao diện Mini App.
- `tests/`: Kiểm thử API và giao diện.

## 2. HƯỚNG DẪN CHẠY TRÊN RENDER / LOCAL:
- Chạy: `python3 app.py`
- Cổng mặc định: 5000 (Render tự nhận biến môi trường PORT).

### Biến môi trường bắt buộc

Không đưa token hoặc mật khẩu vào mã nguồn. Trên Render, tạo các biến sau trong
Dashboard trước khi deploy:

- TELEGRAM_BOT_TOKEN
- TELEGRAM_ADMIN_ID
- SECRET_KEY (chuỗi ngẫu nhiên dài)
- WEB_KEY hoặc ADMIN_PASS

Vì token Telegram cũ từng nằm trong lịch sử Git, hãy thu hồi (revoke) token đó
trong BotFather và tạo token mới trước khi deploy.

/start và /menu sẽ gửi welcome.mp4 trong lần đầu, sau đó Telegram tái sử dụng
file_id đã cache nên phản hồi nhanh hơn và không phải tải lại video.
