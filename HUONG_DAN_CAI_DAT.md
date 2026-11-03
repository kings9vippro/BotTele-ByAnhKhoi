# HƯỚNG DẪN DỰ ÁN GLAZE
Nhà Phát Triển: Dev Khôi Phan & Dev Anh Khôi
Phiên Bản: v1.2.0

## 1. Cấu trúc dự án

- `app.py`: Máy chủ Flask, kết nối và xử lý tác vụ.
- `zalo_core.cpp`: Mã nguồn C++ lưu tham khảo; ứng dụng hiện không nạp tệp nhị phân dựng sẵn.
- `get_ck_im_zalo.py`: Bộ điều khiển Telegram.
- `zalo_login.py`: Đăng nhập QR và quản lý phiên Zalo.
- `templates/miniapp.html`: Giao diện Mini App.
- `static/miniapp.css`, `static/miniapp.js`: Giao diện kính/màu, tab, gọi API có thời hạn chờ và gộp yêu cầu trùng.
- `app_storage.py`: Đường dẫn dữ liệu chung và ghi tệp có phục hồi khi lỗi.
- `miniapp_oauth.py`: Đăng nhập Discord/Facebook bằng OAuth chính thức.
- `command_catalog.py`: Một bảng lệnh dùng chung cho Mini App và menu trong chat.
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

## 3. Đồng bộ dữ liệu và kho tệp

Telegram, Flask và đăng nhập Zalo cùng dùng `DATABASE_PATH`, mặc định là
`APP_DATA_DIR/database.db`. `APP_DATA_DIR` mặc định là thư mục dự án; tệp tải lên
nằm trong `APP_DATA_DIR/uploads`. Nếu đổi đường dẫn, hãy dừng dịch vụ, sao lưu
SQLite nhất quán (gồm dữ liệu WAL chưa checkpoint), rồi chuyển database và uploads
trước khi khởi động lại. Không trỏ các tiến trình vào các database khác nhau.

SQLite dùng WAL, timeout khi có tranh chấp và synchronous NORMAL. Không còn tự
chuyển sang một database rỗng trong `/tmp` khi gặp lỗi. Khi đọc/ghi lỗi, API trả 503;
Mini App giữ số liệu cũ, hiện cảnh báo và cho đồng bộ lại.

Trên **Render Free**, filesystem là tạm: dữ liệu có thể mất khi redeploy hoặc máy
chủ bị thay. Thay đổi code không biến filesystem tạm thành lưu trữ bền vững.
Muốn giữ tài khoản/tệp lâu dài cần cấu hình ổ lưu bền vững hoặc dịch vụ dữ liệu
ngoài phù hợp; chưa có tài nguyên đó được tạo tự động. Bản ghi đã mất từ một
instance cũ không thể khôi phục chỉ từ mã nguồn GitHub.

Tab Tệp lưu lựa chọn Nhây/Ngôn vào `app_settings`, dùng chung với nút chọn tệp
trong Telegram. Chọn mới loại bỏ override cũ che lựa chọn đó. Tên chính xác được
ưu tiên hơn preset khớp một phần; tìm mơ hồ không tự chọn bừa. Thay lựa chọn chỉ áp
dụng khi đọc/chọn nội dung tiếp theo, không tự sửa tác vụ đã chạy với nội dung cũ.
Tệp tối đa 1 MB; tệp đang được chọn không thể xóa cho tới khi chọn tệp khác.
Không xóa tài khoản, quyền truy cập hoặc tệp người dùng khi dọn mã nguồn.

Khi khởi động, chỉ mục tệp cũ được sửa về tên thật trên đĩa (kể cả tên có timestamp)
và đường dẫn thư mục dữ liệu hiện tại. ID và nội dung tệp được giữ nguyên; lựa chọn
đã lưu được chuyển cùng tên. Giá trị `enabled` để NULL từ phiên bản cũ được hiểu
là bật ở cả Telegram và Mini App, không còn lệch bộ đếm giữa hai nơi.

"Đã lưu", "đã bật" và "luồng lắng nghe đang chạy" là ba trạng thái khác nhau.
OAuth được thống kê riêng, không trộn với tài khoản chạy bot hoặc khẳng định đang
online. Nút Đồng bộ đọc lại SQLite; không tự đăng nhập lại mọi tài khoản.

## 4. Discord và Facebook trong Mini App

Đây là đăng nhập trên trang chính thức bằng email hoặc phương thức mà nhà cung
cấp hỗ trợ, **không** phải nhập Gmail/mật khẩu vào Telegram. Không tạo tài khoản,
giả thiết bị, né kiểm tra đăng nhập, xuất cookie hay biến OAuth thành self-bot.
Discord chỉ xin `identify`; Facebook chỉ xin `public_profile`. Muốn gửi tin qua
Discord bot/Messenger Page cần cấu hình ứng dụng và quyền API chính thức riêng.

Tạo ứng dụng tại [Discord Developer Portal](https://discord.com/developers/applications)
và [Meta for Developers](https://developers.facebook.com/apps/). Trên Render cấu hình:

| Biến | Ý nghĩa |
| --- | --- |
| `OAUTH_PUBLIC_BASE_URL` | URL HTTPS chính xác của bot, không có đường dẫn, ví dụ `https://bot.example.com` |
| `OAUTH_ENCRYPTION_KEY` | Khóa Fernet dùng mã hóa khóa OAuth trong SQLite |
| `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` | Thông tin ứng dụng Discord |
| `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET` | Thông tin ứng dụng Meta |
| `FACEBOOK_GRAPH_VERSION` | Phiên bản Graph API còn được hỗ trợ mà Meta app của bạn dùng, dạng `vN.N` |

Tạo Fernet key một lần bằng `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`,
lưu trực tiếp vào biến môi trường, không đưa vào Git hoặc gửi vào chat. Giữ nguyên
khóa này và `SECRET_KEY` qua các lần deploy. Nếu thay khóa mã hóa, cần kết nối lại.

Đăng ký redirect URI tương ứng, khớp tuyệt đối:

- `https://bot.example.com/oauth/callback/discord`
- `https://bot.example.com/oauth/callback/facebook`

Trong Mini App → Tài khoản, nhà cung cấp thiếu cấu hình sẽ hiện "Chưa cấu hình"
kèm tên biến còn thiếu, không báo thành công giả. Khi đã cấu hình, bấm Đăng nhập
→ mở trang ủy quyền → xác nhận quyền → quay lại Mini App và Đồng bộ. Lần mở link
đầu tiên thiết lập phiên HttpOnly trong trình duyệt ngoài, để callback không phụ
thuộc cookie khác của Telegram WebView. Link và state hết hạn sau 5 phút, chỉ dùng
một lần; callback sai trình duyệt bị từ chối. Khóa OAuth được mã hóa trong database,
không trả qua API giao diện. Gỡ liên kết xóa khóa lưu tại bot; có thể thu hồi toàn bộ
quyền ứng dụng trong cài đặt Discord/Facebook.

Ứng dụng Meta ở chế độ phát triển có thể chỉ cho tài khoản test/role đăng nhập;
phải đáp ứng cấu hình/chính sách và quy trình duyệt của nhà cung cấp. Chưa kiểm
thử đăng nhập thật khi chưa có Client/App credentials và callback HTTPS hoạt động.
Không cam kết phiên không bao giờ hết hạn hay Render Free luôn thức.

## 5. Kiểm thử

Chạy `DISABLE_TELEGRAM_BOT=1 DISABLE_BACKGROUND_WORKERS=1 python -m unittest discover -s tests -p 'test_*.py' -v`.
Các kiểm thử dùng database tạm, không đăng nhập tài khoản thật. Bao gồm file chọn
lại sau khởi động, Telegram/Mini App đọc cùng dữ liệu, lỗi ghi, OAuth hết hạn,
callback khác trình duyệt, replay, mã hóa khóa và bảo vệ API.

Giao diện có kiểm thử Playwright tại `tests/miniapp-browser.cjs` (API mô phỏng),
và `tests/miniapp-live.cjs` (API/SQLite thật trên máy local). Test live chỉ chạy
với server local cô lập tại cổng 5873, `APP_DATA_DIR` là thư mục tạm,
`TELEGRAM_BOT_TOKEN=test-token`, `TELEGRAM_ADMIN_ID=123`, `SECRET_KEY=test-secret`,
và hai cờ DISABLE bên trên. Không dùng cấu hình thử nghiệm này trên production.
