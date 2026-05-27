# Hướng dẫn Vận hành & Kiểm thử Hệ thống Cost Control (AWS SAM) cho hackathon-edutech

Bản hướng dẫn này giúp bạn triển khai và chạy thử nghiệm hệ thống **AWS Budgets** cùng hai Lambda kiểm soát chi phí tự động (**Cost Guard** và **Auto Fix Infra**) đã được tích hợp trực tiếp vào tệp hạ tầng `template.yaml` của dự án **hackathon-edutech**.

---

## 1. Cơ chế Hoạt động của Hệ thống

Hệ thống được thiết kế đồng bộ 100% với sơ đồ kiến trúc tổng thể của bạn:
1.  **AWS Budget**: Thiết lập hạn mức ngân sách tháng (ví dụ: **$70.00**). Khi chi phí thực tế chạm mốc **30%**, **50%**, hoặc **80%**, AWS Budgets sẽ bắn một tin nhắn SNS.
2.  **Cost Guard Lambda (`cost_guard.py`)**: Lắng nghe SNS Topic và thực hiện hành động tương ứng:
    *   **Ngưỡng 30%**: Cảnh báo sớm mức Warning (ghi nhận nhật ký).
    *   **Ngưỡng 50%**: Cảnh báo khẩn cấp mức Critical (chuẩn bị hành động).
    *   **Ngưỡng 80% (Khóa Khẩn Cấp)**: Đặt Reserved Concurrency của API Backend Lambda (`studybot-api-<Team>`) về 0 (Chặn đứng mọi request tính phí), tự động gắn chính sách `StudyBotCostDenyPolicy` vào IAM Role để khóa quyền truy cập Bedrock/S3 Put, đồng thời **quét và tự động xóa toàn bộ các Collection OpenSearch Serverless đang chạy** để chặn đứng ngay lập tức chi phí duy trì OCU cực đắt (~$414/tháng).
3.  **Auto Fix Infra Lambda (`auto_fix_infra.py`)**: Lắng nghe qua EventBridge để phát hiện các hoạt động khởi tạo RDS Database lớn, EC2 Instance lớn, hoặc khởi tạo OpenSearch Serverless Collection trái phép từ CloudTrail, tiến hành terminate/delete ngay lập tức để bảo vệ tài khoản khỏi billing shock.

---

## 2. Hướng dẫn Triển khai (Deployment Guide)

Vì các tài nguyên kiểm soát chi phí đã được tích hợp trực tiếp vào **AWS SAM Template**, việc triển khai cực kỳ đơn giản và không cần cài đặt thêm công cụ khác ngoài SAM CLI:

1.  Mở Terminal và di chuyển vào thư mục dự án `hackathon-edutech/`:
    ```bash
    cd "d:\XBrain x AWS Accelerator Internship Program\V. CODE\hackathon-edutech"
    ```
2.  Build ứng dụng SAM để đóng gói toàn bộ code các file (bao gồm `cost_guard.py` và `auto_fix_infra.py` vừa thêm trong thư mục `aws/`):
    ```bash
    sam build
    ```
3.  Triển khai ứng dụng lên AWS:
    ```bash
    sam deploy --guided
    ```
    *(Trong quá trình nhập parameters, nhập các thông tin dự án của bạn bình thường, AWS SAM sẽ tự động khởi tạo hạ tầng cost control đính kèm).*

---

## 3. Quy trình Kiểm thử & Xác minh (Testing & Verification Guide)

Làm sao để chứng minh hệ thống tự động hóa này hoạt động 100% khi nộp bài hoặc thuyết trình slide Capstone? Hãy làm theo các bước mô phỏng thực tế sau:

### Kịch bản 1: Kiểm thử Lambda Cost Guard (Giả lập Vượt Ngưỡng)

Do ngân sách thực tế trong tháng của tài khoản AWS của bạn chắc chắn đã tiêu hao tối thiểu vài xu (ví dụ: $0.10 USD), chúng ta sẽ giả lập vượt ngưỡng bằng cách đặt giới hạn budget cực thấp.

1.  Mở file `template.yaml`, tìm đến tài nguyên `MonthlyCostBudget` (dòng 719-756) và đổi dòng cấu hình `Amount: 70.0` thành **`Amount: 0.01`** (1 cent):
    ```yaml
      MonthlyCostBudget:
        Type: AWS::Budgets::Budget
        Properties:
          Budget:
            BudgetName: !Sub "studybot-monthly-budget-${TeamName}"
            BudgetType: COST
            TimeUnit: MONTHLY
            BudgetLimit:
              Amount: 0.01 # Giảm xuống 1 cent để kích hoạt ngay cảnh báo
              Unit: USD
    ```
2.  Chạy lại lệnh deploy để áp dụng thay đổi:
    ```bash
    sam build && sam deploy
    ```
3.  **Xác nhận kết quả hoạt động:**
    *   **Lambda Cost Guard:** Truy cập AWS CloudWatch Logs của Lambda `studybot-cost-guard-<Team>` để thấy các nhật ký xử lý tương ứng với từng mốc 30%, 50%, và 80%.
    *   **Khóa Backend:** Truy cập AWS Lambda Console của backend API `studybot-api-<Team>` $\rightarrow$ Kiểm tra mục *Concurrency* $\rightarrow$ Xác nhận **Reserved Concurrency đã tự động chuyển về 0** (Chặn đứng mọi request đầu vào).
    *   **Khóa IAM Role:** Truy cập IAM Role `studybot-lambda-role-<Team>` $\rightarrow$ Xác nhận chính sách `StudyBotCostDenyPolicy` đã tự động được đính kèm (Attach) vào role này.
    *   **Xóa OpenSearch Serverless:** Các active OpenSearch Serverless collection sẽ tự động nhận lệnh xóa bỏ hoàn toàn (nếu có).

4.  **Khôi phục trạng thái ban đầu (Rollback):**
    Đổi lại `Amount: 70.0` trong `template.yaml`, chạy `sam build && sam deploy` để khôi phục. Vào Lambda backend gỡ cấu hình Concurrency = 0 và gỡ chính sách Deny khỏi Role của ứng dụng.

---

### Kịch bản 2: Kiểm thử Lambda Auto Fix Infra (Chặn Database/Compute Lạ)

1.  Hãy thử truy cập vào AWS Console bằng tay hoặc dùng AWS CLI để khởi tạo một Database RDS có cấu hình lớn (ví dụ: lớp `db.m5.large`).
2.  Ngay khi quá trình tạo vừa bắt đầu, CloudTrail sẽ ghi nhận sự kiện `CreateDBInstance`.
3.  EventBridge lọc được sự kiện và ngay lập tức trigger **Auto Fix Lambda**.
4.  Lambda sẽ nhận diện DB Instance này không phải loại free-tier/micro được cho phép (`db.t3.micro`/`db.t4g.micro`) và lập tức gọi API `delete_db_instance` để hủy bỏ cơ sở dữ liệu này.
5.  Bạn quay lại RDS Dashboard và sẽ thấy database vừa tạo lập tức chuyển sang trạng thái `Deleting` mà không cần bạn can thiệp thủ công!

---

### Kịch bản 3: Kiểm thử Lambda Auto Fix Infra (Chặn OpenSearch Serverless Lạ)

1.  Hãy thử tạo một OpenSearch Serverless Collection bằng tay trên AWS Console (ví dụ đặt tên: `test-expensive-vector-db`).
2.  Ngay khi quá trình bắt đầu, CloudTrail sẽ ghi nhận sự kiện `CreateCollection`.
3.  EventBridge lọc được sự kiện và ngay lập tức trigger **Auto Fix Lambda**.
4.  Lambda sẽ quét tìm collection vừa tạo theo tên lọc và ngay lập tức gọi API `delete_collection` để xóa bỏ nó, cứu tài khoản của bạn khỏi chi phí 2 OCU đắt đỏ.
5.  Bạn quay lại OpenSearch Dashboards trên Console và sẽ thấy Collection vừa tạo lập tức đổi sang trạng thái `Deleting` chỉ trong vài giây!
