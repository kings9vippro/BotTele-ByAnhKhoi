# HƯỚNG DẪN DỰ ÁN ZENVYRE ULTRA UPGRADED (2026)
Nhà Phát Triển: Dev Khôi Phan & Dev Anh Khôi
Phiên Bản: v2026.25.0 VIP

## 1. CÁC FILE ĐÃ ĐƯỢC NÂNG CẤP & TỐI ƯU HOÁ:
- `app.py`: File máy chủ trung tâm tích hợp Flask, Zalo, Discord, Messenger, Telegram.
  + Đã sửa toàn bộ lỗi code, lỗi đệ quy sticker, lỗi font chữ.
  + Đã tối ưu hoá bộ nhớ Render Free: Tự động dọn RAM (malloc_trim), cắt tỉa bot_logs, checkpoint SQLite WAL, không bao giờ bị vượt GB.
  + Lệnh `.menu` phản hồi siêu tốc 0ms, giao diện menu gọn gàng, tinh tế, không rác chữ.
  + Chạy Đa Acc siêu mượt không bao giờ bị đơ/lag lệnh.
  + Tích hợp đầy đủ lệnh `.lagbox` (pull, giaitan, mention, all) từ C++ Engine Khôi Phan.
  + Nâng cấp Mini App: Đẹp hơn, mượt hơn, font UTF-8 chuẩn 100% không lỗi chữ, hỗ trợ upload file nhây / ngôn dung lượng cao mượt mà.
- `zalo_lag_engine.py`: Động cơ Lag Box độc quyền của Dev Khôi Phan (EXEbykhoiphan).
- `zalo_core.cpp` & `zalo_core.so`: Module C++ nhị phân hiệu năng cao.
- `get_ck_im_zalo.py`: Bộ điều khiển Telegram Bot trung tâm.
- `zalo_login.py`: Hệ thống đăng nhập QR & giữ sống cookie Zalo 24/7.

## 2. HƯỚNG DẪN CHẠY TRÊN RENDER / LOCAL:
- Chạy: `python3 app.py`
- Cổng mặc định: 5000 (Render tự nhận biến môi trường PORT).
