"""Supported command documentation. Author: Dev Anh Khôi. Version: 1.2.0."""

_ALL = ("zalo", "discord", "messenger")
COMMANDS = (
    (".menu", "Mở bảng lệnh", "Hiện các lệnh được hỗ trợ trên nền tảng hiện tại.", _ALL, False),
    (".ping", "Kiểm tra phản hồi", "Đo phản hồi của bộ xử lý; không phải tốc độ mạng tới mọi nền tảng.", _ALL, False),
    (".status", "Thông tin hệ thống", "Xem thông tin trạng thái mà bot đang quản lý.", _ALL, False),
    (".running", "Xem tác vụ", "Liệt kê tác vụ đang chạy.", _ALL, False),
    (".t", "Dừng tại cuộc trò chuyện", "Dừng tác vụ trong cuộc trò chuyện hiện tại.", _ALL, False),
    (".ta", "Dừng toàn bộ", "Dừng tất cả tác vụ do bot quản lý.", _ALL, False),
    (".ds", "Xem kho tệp", "Xem số thứ tự và tên tệp văn bản.", _ALL, False),
    (".chonfile ten.txt", "Chọn tệp", "Lưu lựa chọn chung. Có thể dùng tên chính xác hoặc số thứ tự trong kho tệp.", _ALL, False),
    (".addfile ten.txt | Nội dung", "Thêm tệp văn bản", "Thêm văn bản vào kho. Tệp có thể quản lý trong tab Tệp.", _ALL, False),
    (".sticker", "Tạo nhãn dán", "Gõ lệnh rồi gửi ảnh của chính bạn trong cùng cuộc trò chuyện, trong 2 phút; hoặc trả lời một ảnh.", ("zalo",), False),
    (".qr", "Mở đăng nhập Zalo", "Quét và xác nhận trong ứng dụng Zalo của bạn. Không gửi mã QR cho người khác.", ("zalo",), False),
    (".cp @Tên", "Cấp quyền", "Chỉ chủ tài khoản có thể cấp quyền sử dụng bot.", _ALL, True),
    (".xq @Tên", "Thu hồi quyền", "Chỉ chủ tài khoản có thể thu hồi quyền sử dụng bot.", _ALL, True),
    (".dsq", "Xem danh sách quyền", "Kiểm tra danh sách người đã được cấp quyền.", _ALL, False),
)


def supported_commands(platform=None):
    return [{"usage": usage, "title": title, "description": description,
             "platforms": list(platforms), "owner_only": owner_only}
            for usage, title, description, platforms, owner_only in COMMANDS
            if not platform or platform in platforms]
