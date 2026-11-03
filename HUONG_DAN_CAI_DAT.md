# HƯỚNG DẪN DỰ ÁN GLAZE
Nhà Phát Triển: Dev Khôi Phan & Dev Anh Khôi
Phiên Bản: v1.3.0

## 1. Cấu trúc dự án

- `app.py`: Điểm khởi động nhỏ, vẫn dùng lệnh `gunicorn app:app --config gunicorn.conf.py`.
- `glaze_app.py`: Runtime Flask và kết nối nền, được nạp đúng một lần qua mọi điểm khởi động.
- `bot_settings.py`: Cấu hình token/admin Telegram dùng chung; cấu hình hiện có được giữ nguyên ở đây.
- `task_control.py`: Trạng thái tác vụ và gửi tín hiệu dừng.
- `official_integrations.py`: Discord Interactions và webhook Facebook Page cho lệnh quản lý.
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

## 6. Quản lý trong v1.3.0

### Nhập tài khoản rồi Mini App vẫn báo 0

Xác nhận nhập Zalo trên Telegram nay có `Kho dữ liệu: ...` và tổng tài khoản đọc
lại từ SQLite. Tổng quan Mini App hiện mã kho cùng nút đối chiếu; dán **mã kho**,
không dán cookie/token. Mã khác nhau nghĩa là đang đọc database/instance khác nhau
hoặc database đã bị thay khi dịch vụ được triển khai lại. Mã giống nhau cho biết
cùng kho, nhưng vẫn cần đối chiếu số tài khoản và thao tác xóa đã thực hiện.

Không tự xóa tài khoản khi phiên mất kết nối. Nhập lại cookie cùng UID/IMEI cập
nhật bản ghi hiện có và giữ lựa chọn tắt lệnh. Hàng chờ xử lý lệnh cũng kiểm tra
trạng thái bật/tắt trước khi thực thi. Số "Tài khoản đã lưu" khác với số đang bật.

Bộ xử lý lỗi không còn trả trang quản lý rỗng/HTTP 200 khi gặp ngoại lệ. API trả
lỗi 500, lỗi SQLite 503; lỗi đường dẫn giữ 404. Mini App giữ số liệu đã tải thành
công gần nhất và báo dữ liệu chưa được cập nhật thay vì tạo số liệu 0 từ lỗi.

Render Free vẫn dùng filesystem tạm. Bản này **không thể bảo đảm giữ SQLite qua
redeploy** nếu chưa có ổ lưu bền vững. Khi dùng mount bền vững, đặt APP_DATA_DIR về
mount đó và chuyển dữ liệu trước khi khởi động. Mã kho giúp phát hiện bị đổi nơi
lưu; nó không khôi phục được dữ liệu đã mất của instance cũ.

### Tác vụ và dừng

Tab Tác vụ hiển thị tên lệnh/chế độ, tên đầy đủ kênh đích, tài khoản, số gửi/lỗi
và mã tác vụ. Có bộ lọc đang chạy/đang dừng hoặc cả lịch sử gần đây (tối đa 100).
Nút Dừng gửi tín hiệu ngắt tới worker, chuyển sang Đang dừng nếu worker còn sống,
chỉ hiển thị Đã dừng sau khi worker kết thúc. Một yêu cầu HTTP đã gửi đi có thể
cần chờ timeout/phản hồi; không có cam kết thu hồi tin đã gửi lên nhà cung cấp.

Stopall của một tài khoản nhận diện cả tác vụ có tài khoản đó trong nhóm nhiều
tài khoản. Stopall từ Mini App quản lý toàn bộ tác vụ của tiến trình. Ghi trạng
thái lỗi giữ cờ chờ ghi để lần đồng bộ sau thử lại. Không tự khởi chạy lại tác vụ
cũ khi khởi động máy chủ.

### Form OAuth Discord/Facebook

Trong Tài khoản → Cấu hình ứng dụng, điền App/Client ID, secret, URL HTTPS và
phiên bản Graph API cho Facebook. Máy chủ cần SECRET_KEY cố định. Secret cấu hình
được mã hóa trong SQLite; API giao diện không trả lại secret. Có thể tiếp tục dùng
các biến môi trường ở mục 4. Khi cấu hình qua form, khóa mã hóa phiên OAuth mặc
định được tạo từ SECRET_KEY theo mục đích riêng nếu chưa đặt OAUTH_ENCRYPTION_KEY.
Đổi SECRET_KEY yêu cầu cấu hình/kết nối lại. Lưu cấu hình không tự tạo ứng dụng hay
đăng ký callback bên Discord/Meta.

### Bot Discord và Facebook Page chính thức

OAuth hồ sơ chỉ xác minh danh tính. Muốn điều khiển qua tin nhắn cần cấu hình
riêng phần Bot Discord & Facebook Page trong Mini App:

- Discord: nhập Bot Token, Application Public Key và Discord User ID người quản
  lý. Bot Token được kiểm tra qua API chính thức, mã hóa trước khi lưu. Đặt
  Interactions Endpoint URL là `https://TEN-MIEN/integrations/discord/BOT_ID` trong
  Developer Portal. Bấm Đăng ký 4 lệnh Discord để thêm/cập nhật `/menu`, `/status`,
  `/tasks`, `/stopall`. Không xóa các tên lệnh khác của ứng dụng. Mời ứng dụng vào
  server với scope `applications.commands`. Callback kiểm tra chữ ký Ed25519 và
  danh sách User ID quản lý; phản hồi riêng cho người gọi.
- Facebook: dùng Page Access Token, Page ID, Meta App Secret, Verify Token, phiên
  bản Graph API và PSID người quản lý Page. Cần `pages_messaging`, Page subscription
  và chế độ ứng dụng/quyền đã được Meta cho phép. Callback là
  `https://TEN-MIEN/integrations/facebook/PAGE_ID`; đăng ký sự kiện `messages`. Gửi `menu`,
  `status`, `tasks`, `stopall` tới Page từ PSID đã khai báo. Callback kiểm tra chữ
  ký HMAC; sự kiện trùng được nhận diện trong SQLite. Hàng chờ trả lời tối đa 16,
  hai worker, để giới hạn tải. Lỗi gửi lên Meta được ghi bằng mã trạng thái, không
  ghi token. Có nút xóa cấu hình lưu tại bot khi không dùng nữa.

Có thể lưu nhiều Bot/Page; mỗi kết nối có callback và nút xóa riêng. Dùng callback
hiện trên thẻ kết nối. Với nhiều Page thuộc cùng Meta app, callback chung
`/integrations/facebook` phân luồng theo Page ID và xác minh chữ ký trước xử lý.

Các lệnh quản lý trên không mở quyền chạy lệnh spam/phá nhóm hoặc giả lập phiên
người dùng. Không có máy ảo né xác minh, vượt CAPTCHA hay đăng ký tài khoản hàng
loạt. Chưa kiểm chứng kết nối Discord/Meta thật nếu chưa có credentials/callback
HTTPS và quyền tương ứng; các bài kiểm thử dùng chữ ký thật và API giả lập.

Tệp app.py cũ lớn hơn 1 MB đã nhiều lần bị ghi lại thiếu phần cuối. Khi sửa cấu
hình Telegram hãy dùng bot_settings.py hoặc Environment; không dán đè toàn bộ
runtime glaze_app.py bằng nội dung tải về đã bị rút ngắn. CI kiểm tra cả runtime,
kiểm thử nhập tài khoản và lệnh khởi động Gunicorn trước khi báo đạt.

Build command trong render.yaml nay chạy `python scripts/verify_startup.py` trước
khi cài dependencies. Bộ kiểm tra không khởi chạy bot, không mở database, không
in token; nó kiểm tra cú pháp Python 3.11 và các điểm khởi động thiết yếu để phát
hiện cả trường hợp tệp bị cắt nhưng vẫn là Python hợp lệ. Nếu service Render được
tạo bằng cấu hình thủ công thay vì Blueprint, cần đặt Build Command tương ứng
trong Settings để bước này được áp dụng cho service đó.
