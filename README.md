# LUNA

LUNA là bạn đồng hành trong ngày cho sinh viên. Chat nhìn giờ và nói trước. Future Skill Quest là thế giới RPG riêng, không phải màn hình chính.

本番: https://luna-fsq.onrender.com  
ローカル: http://127.0.0.1:8006

他のエージェントは聞かれてから答える。LUNAは今の時間を見て先に聞き、一言を預かり、次は自分の言葉で聞き返す。

## Chat

LUNA trả lời câu chăm sóc tại chỗ, trước khi gọi mô hình.

- Giờ đang có tiết hoặc ca làm, câu mở là「何かあった？」
- Sau buổi đáng nhớ (発表, 面接, 試験, 課題, 受診) LUNA mời kể lại một câu. 授業 và バイト không dùng lời mời đó.
- Một ngày thường, sau tiết cuối, LUNA hỏi「今日、一言だけ残す？」Câu nói thật được giữ. Sáng hôm sau, trước tiết đầu, câu mở trích lại câu đó. Cùng câu đó được gửi một thông báo, một lần, trước tiết đầu khoảng 40 phút.
- Câu kể mệt có nhiều việc thì chỉ giữ việc nặng nhất, rồi hẹn hỏi lúc việc trên lịch kết thúc, hoặc「明日の朝」.
- Câu hỏi phải làm gì (「何をすればいい」「どうしたら」「方法」「なくしたい」「どうしよう」) nhận một việc gắn với giờ của người đó. 就活 thì mở một đơn. Chưa nêu việc nào thì LUNA hỏi một việc nặng nhất, không liệt kê lời khuyên.
- Việc không có trong danh sách sẵn, như「親とのこと」, vẫn được giữ thành một việc.
-「疲れた」ngắn thì hẹn hỏi lại. Câu nặng thì dừng lời khuyên, ở lại 60 giây, rồi gọi người đã lưu.「大丈夫」thì khép lại.
- Chat ghi một lịch hoặc một khoản chi, rồi nói「予定に入れた。」Ngày trong tuần như「金曜」được đổi thành ngày tới.
- Câu hỏi bài vở, như toán, vẫn được đưa cho mô hình. Bản trên mạng dùng Groq, model `llama-3.1-8b-instant`.

Ngày đầu chỉ hỏi giờ tiết đầu tiên và lưu thành một buổi 授業 90 phút. Giấc ngủ, tiền và các câu còn lại được hỏi mỗi ngày một câu, bắt đầu từ hôm sau. Câu đầu là giờ ngủ.

## Màn hình chính

Thanh dưới có năm chỗ: ホーム, お金, クエスト, ヘルス, メニュー.

Trang chủ hiện nhân vật, câu chào theo giờ, thẻ お金, lịch hôm nay, và nút vào chat.

## Nhân vật

Bảy bạn đồng hành, cùng một việc chăm sóc, khác giọng và cách gọi tên: ルナ, ルノ, レン, ハチ, モモ, タロ, ポンタ. Có thể đổi nhân vật trong メニュー. Người dùng đặt tên mình và tên muốn gọi nhân vật. Giới tính đã lưu thì tên gọi là くん hoặc さん. Nhân vật thú dùng ちゃん, và dùng くん khi giới tính đã lưu là nam.

Nhân vật đổi biểu cảm theo câu vừa nói. Có đọc thành tiếng.

## Lịch, sức khỏe, tiền, mục tiêu

メニュー gom các mục dài:

- スケジュール・ToDo: thêm, xong, xóa buổi. Lịch lặp được kéo dài. Gmail chỉ lấy việc cần làm (họp, nộp, hạn) sau khi người dùng cho phép, không hiện cả hộp thư.
- ヘルスケア: hồ sơ, điểm sức khỏe, BMI, tâm trạng, nhìn lại tuần, radar rủi ro.
- お金・家計: thu chi, điểm tiền, một khoản chi có thể ghi từ chat.
- 目標: nhiều mục tiêu, có tiến độ. Thẻ フューチャーセルフ đặt hai hướng ngày mai cạnh nhau.
- 会話の履歴: các lượt đã nói.
- 朝チェックイン và 夜チェックイン.

## Bạn bè

Mục 友だち:

- Mã QR một lần, hết hạn sau 10 phút. Đọc bằng camera, bằng ảnh, hoặc dán mã. Máy không có trình đọc mã sẵn vẫn đọc được.
-「このあたりの人」chỉ bật khi người dùng chọn. Lưu ô khoảng 1 km trong 20 phút, không lưu kinh độ vĩ độ. Cả hai bên phải bật thì tên mới hiện. Kết bạn cần được chấp nhận.
- Chat chỉ giữa hai người đã là bạn. Có thể cho xem level RPG và số bài đã nộp. Không gửi nội dung nhật ký riêng.

## Future Skill Quest

Mở từ nút クエスト. Đây là lục địa riêng, không trộn vào câu chào hằng ngày.

Chọn lớp 剣士, 魔法使い hoặc 弓使い, rồi chọn nghề. Có bản đồ, bài học, boss, điểm kinh nghiệm và sổ phiêu lưu. Portfolio xuất được thành trang HTML.

## Thông báo

Nhắc lịch và câu sáng dùng thông báo của trình duyệt. Android Chrome nhận được khi đã bật 通知 và đã đăng ký, kể cả lúc đóng tab, nếu lịch nhắc được chạy. iPhone cần thêm ra màn hình chính (iOS 16.4 trở lên). Một tab Safari bị khóa thì không reo.

## Tài khoản

Đăng ký và đăng nhập bằng email. Mật khẩu mới dài tối thiểu 10 ký tự. Sai 8 lần thì khóa 15 phút. Đổi mật khẩu làm token cũ hết hiệu lực. Quên mật khẩu gửi liên kết đặt lại. Có đổi màu giao diện và mục báo lỗi qua email.

Màn hình quản trị chỉ dành cho quản trị viên: danh sách người dùng, khóa tài khoản, đặt lại mật khẩu, xuất dữ liệu. Mật khẩu, vị trí và nội dung chat bạn bè không nằm trong bản xuất đó.
