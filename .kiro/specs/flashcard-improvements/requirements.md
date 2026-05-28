# Tài liệu Yêu cầu

## Giới thiệu

Tính năng này cải tiến chức năng flashcard trong ứng dụng StudyBot (RAG/document Q&A). Hiện tại, flashcard được tạo ra nhưng chỉ lưu trong `localStorage` của trình duyệt và không được lưu trữ lâu dài. Người dùng cũng phải nhập chủ đề thủ công mỗi khi tạo flashcard mới.

Hai cải tiến chính:
1. **Tải flashcard từ S3**: Khi mở trang Leitner Arena, hệ thống tự động tải các flashcard đã lưu từ S3 bucket. Nếu không có flashcard nào, không hiển thị placeholder rỗng.
2. **Tự động lấy topic từ tài liệu đang chọn**: Khi bấm "Generate AI", hệ thống tự động lấy tên tài liệu đang được chọn ở sidebar làm topic thay vì yêu cầu người dùng nhập tay.

## Bảng thuật ngữ

- **Flashcard_Service**: Thành phần backend xử lý việc tạo, lưu và tải flashcard.
- **Leitner_Arena**: Tab giao diện người dùng hiển thị và quản lý flashcard theo hệ thống Leitner SRS.
- **S3_Storage**: Dịch vụ lưu trữ đối tượng AWS S3, được truy cập qua `FlashcardBucket`.
- **Document_Selector**: Thành phần sidebar bên trái cho phép người dùng chọn tài liệu đang hoạt động.
- **Selected_Document**: Tài liệu hiện đang được chọn trong Document_Selector, xác định bởi `doc_id` và `filename`.
- **Flashcard_Key**: Đường dẫn lưu trữ flashcard trên S3, có dạng `{user_id}/flashcards/{doc_id}.json`.
- **Leitner_State**: Trạng thái hiện tại của bộ flashcard bao gồm danh sách thẻ, chỉ số, XP và cấp độ.

---

## Yêu cầu

### Yêu cầu 1: Tải flashcard đã lưu từ S3 khi mở trang

**User Story:** Là một học sinh, tôi muốn các flashcard đã tạo trước đó được tự động tải lại khi tôi mở tab Leitner Arena, để tôi không mất tiến trình học tập giữa các phiên.

#### Tiêu chí chấp nhận

1. WHEN người dùng mở tab Leitner Arena, THE Flashcard_Service SHALL gọi API `GET /flashcards/{doc_id}` để tải flashcard tương ứng với tài liệu đang được chọn.
2. WHEN API trả về danh sách flashcard hợp lệ (mảng không rỗng), THE Leitner_Arena SHALL hiển thị các flashcard đó và ẩn trạng thái rỗng.
3. WHEN API trả về danh sách flashcard rỗng hoặc không có flashcard nào được lưu, THE Leitner_Arena SHALL không hiển thị placeholder rỗng mặc định và giữ nguyên trạng thái chờ.
4. IF không có tài liệu nào được chọn trong Document_Selector, THEN THE Leitner_Arena SHALL không gọi API tải flashcard và không hiển thị nội dung nào.
5. IF API tải flashcard trả về lỗi (HTTP 4xx hoặc 5xx), THEN THE Flashcard_Service SHALL ghi log lỗi và THE Leitner_Arena SHALL hiển thị thông báo lỗi ngắn gọn cho người dùng.
6. WHEN người dùng chuyển sang chọn tài liệu khác trong Document_Selector, THE Leitner_Arena SHALL tự động tải lại flashcard tương ứng với tài liệu mới được chọn.

---

### Yêu cầu 2: Lưu flashcard vào S3 sau khi tạo

**User Story:** Là một học sinh, tôi muốn flashcard vừa tạo được lưu lại trên server, để tôi có thể truy cập lại từ bất kỳ thiết bị nào.

#### Tiêu chí chấp nhận

1. WHEN Flashcard_Service tạo thành công một bộ flashcard mới, THE Flashcard_Service SHALL lưu bộ flashcard đó vào S3_Storage theo Flashcard_Key `{user_id}/flashcards/{doc_id}.json`.
2. THE Flashcard_Service SHALL lưu flashcard dưới định dạng JSON hợp lệ, bao gồm danh sách các đối tượng có trường `front` và `back`.
3. WHEN lưu flashcard vào S3_Storage thành công, THE Flashcard_Service SHALL trả về response bao gồm cả trường `saved: true`.
4. IF lưu flashcard vào S3_Storage thất bại, THEN THE Flashcard_Service SHALL vẫn trả về flashcard đã tạo cho người dùng và ghi log cảnh báo, không làm gián đoạn trải nghiệm người dùng.
5. WHERE S3_Storage được cấu hình (biến môi trường `FLASHCARD_BUCKET` không rỗng), THE Flashcard_Service SHALL sử dụng S3_Storage để lưu flashcard.
6. WHERE S3_Storage không được cấu hình (`FLASHCARD_BUCKET` rỗng), THE Flashcard_Service SHALL bỏ qua bước lưu và chỉ trả về flashcard đã tạo.

---

### Yêu cầu 3: API tải flashcard từ S3

**User Story:** Là một học sinh, tôi muốn có endpoint để lấy flashcard đã lưu theo tài liệu, để frontend có thể hiển thị lại tiến trình học tập của tôi.

#### Tiêu chí chấp nhận

1. THE Flashcard_Service SHALL cung cấp endpoint `GET /flashcards/{doc_id}` để tải flashcard đã lưu.
2. WHEN endpoint nhận request với `doc_id` hợp lệ và flashcard tồn tại trong S3_Storage, THE Flashcard_Service SHALL trả về JSON chứa danh sách flashcard và `doc_id`.
3. WHEN endpoint nhận request với `doc_id` không có flashcard nào được lưu, THE Flashcard_Service SHALL trả về JSON với danh sách flashcard rỗng (`{"doc_id": "...", "flashcards": []}`), không trả về lỗi 404.
4. IF `doc_id` không thuộc về `user_id` hiện tại, THEN THE Flashcard_Service SHALL trả về danh sách flashcard rỗng.
5. IF S3_Storage không được cấu hình, THEN THE Flashcard_Service SHALL trả về danh sách flashcard rỗng.

---

### Yêu cầu 4: Tự động lấy topic từ tài liệu đang chọn

**User Story:** Là một học sinh, tôi muốn khi bấm "Generate AI" hệ thống tự động dùng tên tài liệu đang chọn làm chủ đề, để tôi không cần nhập topic thủ công mỗi lần.

#### Tiêu chí chấp nhận

1. WHEN người dùng bấm nút "Generate AI" trong Leitner_Arena và có một Selected_Document trong Document_Selector, THE Leitner_Arena SHALL tự động sử dụng `filename` của Selected_Document làm giá trị topic (bỏ phần mở rộng file như `.pdf`, `.txt`, `.md`).
2. WHEN người dùng bấm nút "Generate AI" và không có tài liệu nào được chọn, THE Leitner_Arena SHALL hiển thị thông báo yêu cầu người dùng chọn tài liệu trước, không gọi API.
3. THE Leitner_Arena SHALL ẩn ô nhập topic thủ công (`input#flashcard-topic`) khi có Selected_Document.
4. THE Leitner_Arena SHALL hiển thị tên topic đang được sử dụng (tên tài liệu đã chọn) dưới dạng nhãn thông tin bên cạnh nút "Generate AI".
5. WHEN người dùng chọn tài liệu khác trong Document_Selector, THE Leitner_Arena SHALL cập nhật nhãn topic hiển thị tương ứng với tài liệu mới.
6. WHERE người dùng muốn nhập topic tùy chỉnh, THE Leitner_Arena SHALL cung cấp tùy chọn để hiển thị lại ô nhập topic thủ công.

---

### Yêu cầu 5: Đồng bộ Leitner State với flashcard từ S3

**User Story:** Là một học sinh, tôi muốn tiến trình Leitner (box, XP, level) được giữ nguyên khi tải lại flashcard từ server, để việc học tập liên tục không bị gián đoạn.

#### Tiêu chí chấp nhận

1. WHEN Leitner_Arena tải flashcard từ S3_Storage, THE Leitner_Arena SHALL hợp nhất (merge) dữ liệu flashcard từ server với Leitner_State hiện tại trong localStorage, ưu tiên giữ nguyên giá trị `box` của từng thẻ nếu đã tồn tại.
2. WHEN flashcard tải từ S3_Storage chứa thẻ mới chưa có trong Leitner_State, THE Leitner_Arena SHALL thêm thẻ mới đó vào Leitner_State với `box = 1`.
3. WHEN flashcard tải từ S3_Storage không chứa thẻ nào mới so với Leitner_State hiện tại, THE Leitner_Arena SHALL giữ nguyên Leitner_State không thay đổi.
4. THE Leitner_Arena SHALL lưu Leitner_State đã hợp nhất vào localStorage sau mỗi lần tải flashcard từ S3_Storage thành công.
