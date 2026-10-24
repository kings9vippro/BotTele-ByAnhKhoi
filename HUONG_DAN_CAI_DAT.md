# 🤖 HƯỚNG DẪN VẬN HÀNH BOT TREO 4APP 🇻🇳 (TELEGRAM BOT CONTROLLER)

## 1. Cấu Hình Đã Tích Hợp Sẵn
- **Telegram Bot Token**: `8917587021:AAGnf2uUmNLI1r747luw8BVGi_hr3jBzWpw`
- **Admin Chính (Root Admin ID)**: `8827605973`
- **Video Chào Mừng**: `welcome.mp4` (Tự động gửi kèm ở đầu bảng điều khiển giống hệt ảnh mẫu, tự động cache `file_id` giúp mở menu trong `0.05s`).
- **Tối Ưu Hoá Render**: Đã gỡ bỏ hoàn toàn giao diện Web nặng nề (~4.700 dòng HTML/CSS/JS), chỉ giữ lại cổng Keep-Alive siêu nhẹ (`< 1.2 KB`) tại `/` và `/healthz` để nuôi sống dịch vụ trên Render Free 24/7 mà không tốn RAM/CPU.

## 2. Giao Diện 3 Tab & 32 Chức Năng VIP Trên Bot Telegram
Gõ `/start` hoặc `/menu` trong Bot Telegram để mở bảng điều khiển:
- **🔘 Chức Năng (32 item chia 4 trang)**:
  - **Trang 1/4**: `🥀 Treo Ngôn Đỏ`, `🌈 Treo Đa Màu`, `🎬 Treo Ngôn GIF`, `✨ Chữ Đổi Từng Màu`, `💬 Treo Nhây`, `🏷️ Nhây Tag Tên`, `📢 Nhây Tag All Ẩn`, `👻 Nhây Tag Tên Ẩn`
  - **Trang 2/4**: `🚀 Siêu Xả Đa Box`, `⚡ Combo 3 Câu/Nhịp`, `🔥 Nhây Gộp 2 Câu`, `🔢 Treo Số Liên Hoàn`, `🎯 Số Kèm Tag`, `👑 Số Fake Tên`, `🌪️ Bão Icon VIP`, `💥 Nhây Sát Thương`
  - **Trang 3/4**: `📊 Tạo Poll Tự Động`, `⌨️ Hiệu Ứng Typing`, `✏️ Đổi Tên Box`, `📋 Giao Việc To-Do`, `🏦 Thẻ Ngân Hàng`, `🪪 Gửi Danh Thiếp`, `🎨 Đổi Nền MQTT`, `🔗 Chia Sẻ Link`
  - **Trang 4/4**: `🏷️ Đổi Biệt Danh`, `🛡️ Chặn & Bám Sát`, `🌐 Xoay Vòng Proxy`, `🛡️ Anti Cấm Chat Box`, `⏱️ Chỉnh Tốc Độ Delay`, `🎨 Chế Độ Màu Chữ`, `🔤 Cỡ & Kiểu Chữ`, `🛑 Dừng Tất Cả (.ta)`
- **⚪ Quản Lý (6 mục)**:
  - `➕ Thêm ID Người Dùng`: Cấp quyền cho ID Telegram/Zalo được phép sử dụng Bot (hoặc gõ `/addid <ID> [Tên]`).
  - `➖ Xoá ID Người Dùng`: Hiển thị danh sách nút bấm từng ID đang có quyền — bấm vào ID nào là **xoá ngay lập tức** quyền sử dụng Bot của ID đó (hoặc gõ `/delid <ID>`).
  - `📋 Danh Sách ID VIP`: Kiểm tra toàn bộ ID đang được phép dùng Bot.
  - `📲 Quét QR Zalo PC`: Tạo mã QR Zalo PC chuẩn (`zalo.me/pc` -> `chat.zalo.me`), tự động nạp Cookie + IMEI + khóa `zpw_enk` và sống trực tiếp trong Acc 24/7.
  - `🔍 Check & Cứu Cookie`: Kiểm tra toàn bộ tài khoản Zalo Live/Die và tự động làm mới `zpw_sek`.
  - `🗂️ Quản Lý Acc & File`: Xem/xoá tài khoản và quản lý kho 8 file kịch bản `.txt`.
- **⚪ Tiện Ích (6 mục)**:
  - `🔐 Tạo Mã 2FA OTP`, `🤖 Trợ Lý Meta AI`, `🎯 Lấy Token Discord`, `🍪 Lấy Cookie FB`, `✨ Đổi Font Chữ VIP`, `📊 Trạng Thái Hệ Thống`.

## 3. Chế Độ Chữ Đổi Từng Màu (0% Chữ Trắng) & Anti Cấm Chat Box Zalo
- **Chữ Đổi Từng Màu (`word_rainbow`)**: Mặc định mọi câu treo/nhây đều tự động đổi màu từng từ (hoặc từng chữ cái nếu câu chỉ có 1 từ) qua 4 mã màu chuẩn gốc Zalo (`db342e` Đỏ, `f27806` Cam, `f7b503` Vàng, `15a85f` Xanh Lá). Tuyệt đối không bao giờ bị lỗi chữ trắng trên Zalo! Chỉ các tin nhắn thông báo chức năng hệ thống (`.menu`, `.ping`, `.status`) mới giữ chữ trắng.
- **Anti Cấm Chat Box Zalo (`ZaloSmartAntiBanEngine`)**: Tự động điều tiết nhịp gửi theo từng Box (`Sliding-Window Box Pacing`), tự động gửi xung `typing` định kỳ như người thật, xoay vòng đa cổng (`tt-group-wpa` / `wpa`) và gắn chữ ký tàng hình biến thiên độ dài giúp chống khóa chat trong nhóm Zalo.
