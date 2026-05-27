# BẢN DRAFT EVIDENCE PACK & SLIDES — PHÂN KHU COST CONTROL (NHÓM CAPSTONE W7)

> **Tác giả:** Người phụ trách phân khu Budget & Cost Control
> **Mục tiêu:** Cung cấp sẵn tài liệu báo cáo (Evidence Pack §4, §6.5, §8) và nội dung Slides thuyết trình để bạn copy-paste hoặc dùng làm tài liệu trả lời Q&A trực tiếp trước Ban giám khảo.

---

## 1. NỘI DUNG TRÌNH BÀY TRÊN SLIDES (Cho slide Cost & Lessons Learned)

### Slide Title: Hệ Thống Giám Sát Chi Phí & Bảo Vệ Tài Khoản Tự Động (Active Cost Guardrails)

*   **Kiến trúc chốt chặn (Security & Cost Gateways):**
    *   **AWS Budget:** Đặt hạn mức **$70.00 USD/tháng** (đồng bộ với ngân sách Hackathon tối đa $100).
    *   **Tiered Threshold Alerts:** Thiết lập 3 mốc cảnh báo thực tế (ACTUAL) bằng SNS Topic:
        *   **30% ($21.00):** Cảnh báo sớm mức cảnh giác (Warning).
        *   **50% ($35.00):** Cảnh báo nguy cơ vượt hạn mức (Critical).
        *   **80% ($56.00):** Kích hoạt **Emergency System Freeze (Khóa khẩn cấp)**.
*   **Kịch bản Tự động hóa Khóa Khẩn cấp (80%+):**
    *   **Lambda Cost Guard** lập tức đặt **Reserved Concurrency của Lambda Backend về 0** $\rightarrow$ Dừng ngay lập tức mọi request tính phí phát sinh từ API, trả về `RateExceededException` với chi phí tính toán = $0.
    *   Tự động **Attach Managed Policy `StudyBotCostDenyPolicy`** vào IAM Execution Role để chặn đứng quyền gọi API Bedrock (`bedrock:*`, `aoss:*`) và S3 Put.
    *   **Xóa bỏ khẩn cấp OpenSearch Serverless** để dập tắt chi phí OCU duy trì rất lớn ($414/tháng).
*   **Cơ chế Auto Fix Infra (Chặn đứng chi phí ngầm từ tài nguyên lạ):**
    *   EventBridge bắt sự kiện `RunInstances`, `CreateDBInstance`, và `CreateCollection` qua CloudTrail.
    *   Tự động xóa/terminate ngay lập tức các EC2, RDS lớn hoặc OpenSearch Serverless Collection lạ ngoài danh sách whitelist free-tier (`t2/t3.micro` cho EC2, `db.t3/t4g.micro` cho RDS) chỉ trong **15 - 30 giây** từ khi khởi tạo!

---

## 2. NỘI DUNG CHO BÁO CÁO EVIDENCE PACK (`W7_evidence.md`)

Bạn có thể gửi khối markdown này cho Trưởng nhóm để ghép trực tiếp vào tài liệu `W7_evidence.md` nộp bài:

```markdown
### 4. Cost Discipline & Budgets (Kỷ luật Ngân sách)

Hệ thống của chúng tôi thiết lập cơ chế giám sát chủ động và phản ứng nhanh (Proactive & Reactive Remediation) để bảo vệ tài khoản AWS cá nhân khỏi rủi ro billing shock:

*   **AWS Budget Limit:** $70.00 USD (Monthly).
*   **SNS Topic:** `studybot-budget-alerts-${TeamName}` kết nối trực tiếp AWS Budgets và Lambda `studybot-cost-guard`.
*   **Các mốc phản ứng (Remediation Actions):**
    1.  **30% ($21.00 ACTUAL):** Ghi nhận cảnh báo Warning vào hệ thống Log tập trung.
    2.  **50% ($35.00 ACTUAL):** Gửi cảnh báo khẩn cấp mức độ Critical để quản trị viên kiểm tra hoạt động tài khoản.
    3.  **80% ($56.00 ACTUAL):** Chế độ đóng băng hệ thống (Emergency Stop):
        *   Đặt `ReservedConcurrentExecutions = 0` trên Lambda Backend API để ngắt kết nối xử lý tính phí đầu vào.
        *   Đính kèm IAM Deny Policy (`StudyBotCostDenyPolicy`) nhằm chặn mọi API Call đến Amazon Bedrock, OpenSearch Serverless, và S3 Write.
        *   Xóa bỏ mọi OpenSearch Serverless Collection đang chạy để tránh chi phí nhàn rỗi nhạy cảm (~$414/tháng).

---

### 6.5 Architectural Decision Blocks (Quyết định Kiến trúc & Số liệu)

#### DECISION 1: Xây dựng cơ chế Remediation tự động khóa Concurrency của Lambda về 0 và chặn IAM thay vì xóa ứng dụng khi vượt ngưỡng 80%

*   **ALTERNATIVES CONSIDERED:**
    *   *Xóa hoàn toàn CloudFormation Stack:* Bị loại trừ vì sẽ làm mất cấu hình hệ thống, phá hỏng trạng thái bền vững của cơ sở dữ liệu, và không thể khôi phục nhanh (DR) trong buổi Demo.
    *   *Chỉ gửi Email thông báo:* Bị loại trừ vì con người có độ trễ phản hồi (trung bình vài giờ đến nửa ngày), trong khi các API Bedrock hoặc RDS cấu hình lớn có thể tiêu hao hàng chục USD chỉ trong vài phút.
*   **MEASUREMENT:**
    *   Thời gian từ lúc ngân sách vượt ngưỡng 80% đến khi hệ thống đóng băng hoàn toàn: **< 3 giây** (Được đo lường qua độ trễ kích hoạt Lambda Cost Guard).
    *   Chi phí tính toán phát sinh sau khi đóng băng: **$0.00 USD** (Lambda bị giới hạn về 0 concurrency sẽ lập tức từ chối request ở tầng Gateway mà không cần khởi tạo môi trường runtime).
*   **EVIDENCE:**
    *   Log CloudWatch của Lambda `CostGuardFunction` xác nhận gọi thành công `PutFunctionConcurrency` và `AttachRolePolicy`.
*   **TRADE-OFF ACCEPTED:**
    *   Khi hệ thống đóng băng, người dùng cuối sẽ gặp lỗi `RateExceededException` (502/429) và không thể sử dụng dịch vụ cho đến khi Quản trị viên can thiệp mở khóa thủ công.

#### DECISION 2: Tự động phát hiện và hủy bỏ ngay lập tức các OpenSearch Serverless, EC2, RDS cấu hình lớn hoặc lạ ngoài whitelist của Hackathon

*   **ALTERNATIVES CONSIDERED:**
    *   *Sử dụng AWS Config Rule:* Bị loại trừ do AWS Config hoạt động theo chu kỳ quét định kỳ (khoảng 15 phút đến 1 giờ), quá chậm để ngăn chặn chi phí phát sinh tức thì từ các instance đắt đỏ.
    *   *Không can thiệp tự động (Chỉ cảnh báo):* Bị loại trừ vì OpenSearch Serverless tiêu tốn tối thiểu $13.82/ngày cho 2 OCU nhàn rỗi và $414/tháng nếu quên xóa sau buổi Demo.
*   **MEASUREMENT:**
    *   Thời gian phản ứng (Detection to Destruction latency): **< 20 giây** kể từ khi sự kiện `CreateCollection` hoặc `CreateDBInstance` xuất hiện trên CloudTrail.
    *   Số tiền tiết kiệm được cho mỗi lần ngăn chặn thành công tài nguyên lớn (ví dụ: `db.m5.large` RDS hoặc AOSS Collection nhàn rỗi chạy qua đêm): **~$15.00 - $30.00 USD / đêm**.
*   **EVIDENCE:**
    *   CloudWatch log của `AutoFixInfraFunction` ghi nhận luồng: Nhận CloudTrail Event $\rightarrow$ Phát hiện sai Whitelist $\rightarrow$ Gọi API `delete_collection` / `delete_db_instance` thành công.
*   **TRADE-OFF ACCEPTED:**
    *   Mất toàn bộ dữ liệu đang thử nghiệm của thành viên nếu họ vô tình tạo tài nguyên ngoài whitelist mà chưa kịp sao lưu.

---

### 8. Teardown Plan & Verification (Kế hoạch dọn dẹp sạch tài nguyên)

Để đảm bảo không phát sinh chi phí sau Hackathon và đạt điểm tối đa tiêu chí dọn dẹp (Teardown Mandate - Hạn CN 1/6 EOD):

1.  **Empty S3 Buckets:** Tiến hành xóa sạch toàn bộ files trong S3 vector store và static hosting trước khi dọn dẹp.
2.  **Delete SAM Stack:** Thực thi lệnh xóa toàn bộ tài nguyên đã deploy thông qua CloudFormation:
    ```bash
    aws cloudformation delete-stack --stack-name studybot-edutech
    ```
3.  **Xác minh dọn dẹp thủ công trên AWS Console theo thứ tự:**
    *   *OpenSearch Serverless (AOSS):* Truy cập Amazon Bedrock $\rightarrow$ Knowledge Bases $\rightarrow$ Xác nhận không còn Collection nào đang chạy.
    *   *RDS & EC2:* Xác nhận trạng thái `Terminated` (EC2) và không còn instance nào trong bảng RDS.
    *   *VPC & NAT Gateway:* Xác nhận không còn NAT Gateway nào đang Active (tránh chi phí chạy ngầm $1.08/ngày).
4.  **Chụp ảnh xác nhận:** Chụp màn hình trang Cost Explorer gần bằng **$0.00** vào sáng thứ Hai (2/6) và commit vào Git repo tại `docs/teardown_confirmed.png`.
```

---

## 3. CÂU HỎI & TRẢ LỜI NHANH (Q&A CHEAT SHEET) CHO BUỔI VẤN ĐÁP CÁ NHÂN

**Q1: Tại sao em lại chọn giải pháp set Reserved Concurrency của Lambda Backend về 0 để đóng băng hệ thống thay vì xóa luôn ứng dụng?**
*   *Trả lời:* Xóa Stack hoặc xóa ứng dụng sẽ làm mất hoàn toàn dữ liệu và hạ tầng, tốn rất nhiều thời gian để deploy lại từ đầu và cấu hình lại. Trong khi đó, việc đưa Reserved Concurrency về 0 sẽ ngắt dòng request tức thì tại tầng Gateway, không tốn bất kỳ chi phí tính toán nào, và khi cần khôi phục lại (ví dụ sau khi đã nạp thêm ngân sách), admin chỉ cần gỡ giới hạn concurrency về mặc định là hệ thống hoạt động bình thường ngay lập tức.

**Q2: Làm sao Lambda `auto_fix_infra` của bạn bắt được hành vi tạo tài nguyên trái phép nhanh như vậy?**
*   *Trả lời:* Hệ thống của em sử dụng luồng: CloudTrail ghi nhận API call $\rightarrow$ EventBridge bắt sự kiện thời gian thực (Real-time Event-Driven) theo mẫu EventPattern lọc cụ thể các API như `RunInstances`, `CreateDBInstance`, `CreateCollection` $\rightarrow$ Kích hoạt Lambda xử lý trong chưa đầy 1 giây. Nhờ đó, tổng thời gian từ lúc tài nguyên bắt đầu khởi tạo đến khi bị xóa chỉ mất từ 15 đến 30 giây.

**Q3: OpenSearch Serverless tốn bao nhiêu chi phí nếu để chạy không qua đêm? Hệ thống của em giải quyết nó thế nào?**
*   *Trả lời:* OpenSearch Serverless có mức chạy tối thiểu là 2 OCU (1 cho index, 1 cho search) với giá $0.288/OCU-giờ ở Singapore, tức là khoảng $13.82/ngày và hơn $414/tháng kể cả khi không có bất kỳ truy vấn nào. Hệ thống của em giải quyết bằng cách: (1) Ở ngưỡng 80% ngân sách, Cost Guard sẽ tự động list và xóa sạch Collection; (2) Ở mức giám sát hạ tầng hàng ngày, Auto Fix Lambda sẽ tự động tiêu hủy bất kỳ Collection nào mới tạo trái phép để tránh việc quên tắt gây phát sinh hóa đơn lớn.
