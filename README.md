# NHK — Hệ Thống Điều Phối Đa Tài Khoản (100% Máy Tính Singapore • Check Cookie/IMEI Sống/Die • Đa Acc 0ms)

Tài liệu kỹ thuật tổng hợp các nâng cấp trên `zalo_login.py`, `get_ck_im_zalo.py`, và `app.py`:

## 1. Tất Cả Máy Tính Đổi Luân Phiên Đặt Tại Duy Nhất Địa Điểm Singapore (`zalo_login.py` & `app.py`)
- Toàn bộ 12 cấu hình máy tính PC/Mac luân phiên (`sg_vip`, `sg_mac_pro`, `sg_mac_air`, `sg_imac`, `sg_mac_studio`, `sg_rog_zephyrus`, `sg_rog_strix`, `sg_msi_titan`, `sg_dell_precision`, `sg_thinkpad_z16`, `sg_hp_spectre`, `sg_asus_proart`) đều cố định tại **Singapore (SG)**, đồng bộ hoàn toàn với máy chủ Render Singapore.
- Khắc phục triệt để lỗi máy tính tự thoát ra khỏi tài khoản sau khi quét QR và lỗi `UID: zalo_... (0 nhóm)` bằng luồng `continue=https://chat.zalo.me/` ➔ `jr.chat.zalo.me/jr/pushsession` thu hoạch `zpw_sek` thật + `getLoginInfo` lấy `zpw_enk` thật và `UID` số thật.

## 2. Check Cookie + IMEI Zalo Sống (Trong Acc) hay Die & Giữ Sống Đa Hoạt Động 24/7 (`zalo_login.py` & `get_ck_im_zalo.py`)
- Hàm `check_zalo_cookie_imei_live()` kiểm tra trực tiếp trên máy chủ Zalo WPA (`getLoginInfo` + `group/getlg/v4`) xem thiết bị máy tính lấy Cookie + IMEI đó **có đang nằm trong tài khoản Zalo và hoạt động ổn định hay không**:
  - Nếu thiết bị máy tính đang ở trong Acc: báo **🟢 SỐNG (ON)** kèm số lượng nhóm thực tế và tự động đưa vào `ZaloPCSessionKeeper` để chạy đa hoạt động liên tục (`getServerInfo`, `preloadconvers/get-last-msgs`, `group/getlg/v4`) mỗi 18 giây.
  - Nếu người dùng đã đăng xuất thiết bị đó khỏi Acc (hoặc phiên đã ngắt): báo **🔴 DIE (OFF)** ngay lập tức.
- Trên Bot Telegram (`get_ck_im_zalo.py`):
  - Lệnh `/check` và nút **🔍 Check Cookie + IMEI Zalo (Sống/Die)**: kiểm tra toàn bộ Cookie + IMEI trong kho hoặc do người dùng dán/gửi file `.txt`.
  - Lệnh `/token` và nút **🔑 Giữ Sống Token / Cookie 24/7**: chỉ cần gửi Token Discord hoặc Cookie+IMEI Zalo, hệ thống tự động khóa định danh thiết bị trong SQLite Vault và chạy đa hoạt động liên tục 24/7 để dù đăng xuất/đăng nhập lại cũng không báo thay đổi Cookie mới.

## 3. Chọn Nhanh N Acc, N Box, Nút "Cho Phép Acc Sử Dụng Lệnh" & Đa Acc Bắn Đồng Loạt 0ms (`app.py`)
- **Chọn số lượng Acc & số lượng Box trên Web**: tích hợp các nút chọn nhanh `1, 5, 10, 20, 50, N Acc` và `1, 5, 10, 20, 50, 100, 500, N Box`.
- **Nút "Cho Phép Acc Sử Dụng Lệnh"**: bật/tắt tức thì quyền nhận lệnh (`chat_cmd_enabled`) và quyền cho nhóm dùng lệnh (`allow_all_cmd`) cho từng Acc, cho các Acc đang chọn, hoặc toàn bộ Acc mà không cần tải lại trang.
- **Xoá hoàn toàn chế độ tự thêm icon ngẫu nhiên** (`icon_count = 0`, `use_emoji = False`) và **xoá độ trễ giữa các Acc** (`stagger_base = 0.0`, `get_fair_pacing_pause = 0.0`) kết hợp tự động thu thập Proxy/API nền & tối ưu bộ nhớ nhẹ cho Render Free.
