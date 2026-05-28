# Tài Liệu Bằng Chứng W7 - StudyBot / Trợ Lý Học Tập AI

> Trạng thái: bản nháp cho lần nộp cuối cùng. Thay thế mọi `TODO` bằng giá trị triển khai thực tế và thêm ảnh chụp màn hình vào thư mục `docs/evidence/`.

## 1. Trang Bìa

| Trường | Giá trị |
|---|---|
| Nhóm | TODO: G15 |
| Thành viên | TODO: tên các thành viên |
| Lĩnh vực | EduTech - Trợ Lý Học Tập AI |
| Ca sử dụng | Tải lên file PDF/slide/ghi chú văn bản bài giảng, sau đó đặt câu hỏi, tạo flashcard/bài kiểm tra và tiếp tục học từ trạng thái đã lưu. |
| URL công khai | TODO: URL HTTPS frontend cuối cùng dùng cho trainer, ưu tiên CloudFront nếu frontend deploy riêng đã hoạt động |
| API URL | `https://1lse4odraj.execute-api.ap-southeast-1.amazonaws.com` hoặc TODO: URL API Gateway cuối cùng |
| GitHub repo | TODO: URL repo công khai |
| AWS region | `ap-southeast-1` |
| Tổng chi phí | TODO: USD từ ảnh chụp màn hình Cost Explorer cuối cùng |
| Video demo | TODO: `docs/demo.mp4` hoặc liên kết YouTube không công khai |

Ảnh chụp màn hình bắt buộc cho phần này:
- `docs/evidence/01_live_url_loaded.png` - ứng dụng HTTPS hiển thị cho người đánh giá được tải trên trình duyệt.
- `docs/evidence/02_repo_readme.png` - repo GitHub công khai với README, kiến trúc, hướng dẫn cài đặt, dọn dẹp.

## 2. Bài Thuyết Trình và Tầm Nhìn

StudyBot giúp người học biến tài liệu bài giảng thành các tài sản học tập chủ động. Người học tải lên một file PDF, file xuất từ slide, hoặc ghi chú dạng văn bản, sau đó nhận được phần hỏi đáp bám sát nội dung, flashcard, bài kiểm tra, ghi chú Cornell và phản hồi đánh giá chất lượng truy xuất từ chính tài liệu học tập đó.

Đối tượng người dùng mục tiêu là sinh viên đại học, người tự học và những người ôn thi đã có sẵn ghi chú nhưng mất thời gian chuyển đổi chúng thành quy trình ôn tập. Dự án này quan trọng vì một sản phẩm hữu ích không chỉ là "trò chuyện với PDF"; nó là một vòng lặp học tập: tải lên, đặt câu hỏi, tạo tài liệu ôn tập, ôn tập, và quay lại sau với trạng thái được giữ nguyên.

Ảnh chụp màn hình bắt buộc:
- `docs/evidence/03_upload_flow.png` - chọn/tải file lên thành công.
- `docs/evidence/04_ai_answer_with_context.png` - câu trả lời hỏi đáp được tạo từ tài liệu đã tải lên.
- `docs/evidence/05_flashcards_or_quiz.png` - flashcard/bài kiểm tra được tạo hiển thị trên UI.

## 3. Kiến Trúc

### Sơ Đồ Cuối Cùng

Sơ đồ kiến trúc cuối cùng: TODO: thêm hình ảnh tại `docs/evidence/architecture.png`.

Kiến trúc được triển khai là serverless (không máy chủ):

| Năng lực | Dịch vụ sử dụng | Bằng chứng |
|---|---|---|
| 1. Giao diện người dùng | CloudFront + S3 static frontend, deploy ngoài SAM backend stack | TODO: ảnh chụp màn hình CloudFront distribution |
| 2. Tính toán ứng dụng | API Gateway HTTP API + AWS Lambda (`studybot-query`, `studybot-upload`, `studybot-core`) | TODO: ảnh chụp màn hình Lambda/API Gateway |
| 3. Tính năng AI / ML | Amazon Bedrock Claude Sonnet theo `samconfig.toml` hiện tại + Bedrock Knowledge Base / gọi trực tiếp InvokeModel làm dự phòng | TODO: quyền truy cập mô hình Bedrock + kết quả UI |
| 4. Lưu trữ dữ liệu | DynamoDB (trạng thái người dùng/tài liệu/truy vấn); S3 JSON cho quiz đã lưu; tài liệu upload lưu trong S3 | TODO: ảnh chụp màn hình item DynamoDB + đối tượng S3 |
| 5. Lưu trữ Object | Bucket S3 cho tài liệu và bucket S3 cho flashcard/bài kiểm tra | TODO: danh sách đối tượng trong bucket S3 |
| 6. Nền tảng mạng | VPC, private subnet, Lambda SG, S3/DynamoDB gateway endpoints, Bedrock interface endpoints | TODO: ảnh chụp màn hình VPC/subnet/endpoint |
| 7. Danh tính & truy cập | Vai trò thực thi Lambda cấp quyền tối thiểu (IAM least-privilege); người dùng demo thông qua `X-User-Id` | TODO: ảnh chụp màn hình IAM policy |

### Các Quyết Định Dịch Vụ

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| Tính toán | Chia Lambda thành các hàm query/upload/core | Giữ chi phí lúc rảnh gần như bằng 0 và cho phép các route tải lên/AI nặng có thời gian timeout dài hơn mà không cần tăng kích thước cho các route health/list. |
| Cổng API | API Gateway HTTP API | Rẻ và đơn giản hơn REST API cho ứng dụng request/response này. |
| Frontend | S3 + CloudFront | HTTPS công khai, chi phí thấp, không cần quản lý máy chủ. |
| Database | DynamoDB on-demand | Các mẫu truy cập là dạng key-value/trạng thái người dùng-tài liệu; không cần kết nối quan hệ cho bản demo. |
| Lưu trữ Object | S3 | PDF, nội dung trích xuất, và JSON quiz đã lưu đều là dữ liệu blob/tài liệu. |
| Mô hình AI | Claude 3.5 Sonnet theo cấu hình deploy hiện tại | Chất lượng câu trả lời tốt hơn cho demo cuối; nếu chi phí là ưu tiên chính thì đổi `AiModelId` về Haiku và cập nhật evidence. |
| RAG | Bedrock Knowledge Base, kết hợp dự phòng từ khóa nội bộ trong code | Câu trả lời bám sát tốt hơn khi KB sẵn sàng; dự phòng giúp đường dẫn demo vẫn hoạt động nếu việc nhập dữ liệu vào KB gặp sự cố. |
| Mạng | Private Lambda subnet + VPC endpoints, không dùng NAT Gateway | Gateway endpoints cho S3/DynamoDB là miễn phí; interface endpoints cho Bedrock giúp tránh chi phí cố định của NAT. |
| Giám sát | Dashboard CloudWatch, cảnh báo, log, custom metrics | Cung cấp bằng chứng vận hành và hỗ trợ tùy chọn Full Observability (Khả năng quan sát toàn diện). |
| IaC | AWS SAM / CloudFormation trong `template.yaml` | Triển khai có thể lặp lại và dễ dàng dọn dẹp thông qua việc xóa stack. |

### Sự Đánh Đổi

1. Lambda so với EC2/ECS: chọn Lambda vì tốc độ trong 48 giờ và chi phí rảnh thấp. Chấp nhận các hạn chế về thời gian khởi động lạnh (cold start) và giới hạn timeout.
2. DynamoDB so với RDS: chọn DynamoDB vì trạng thái người dùng và metadata tài liệu là những mẫu truy cập đơn giản. Chấp nhận khả năng truy vấn đột xuất (ad-hoc) yếu hơn.
3. Bedrock KB so với gọi InvokeModel trực tiếp: chọn KB để truy xuất bám sát nội dung. Giữ phương án dự phòng gọi trực tiếp/cục bộ vì thiết lập và nhập dữ liệu KB có thể là phần phụ thuộc rủi ro nhất khi demo.

Ảnh chụp màn hình bắt buộc:
- `docs/evidence/06_architecture_diagram.png`
- `docs/evidence/07_api_gateway_routes.png`
- `docs/evidence/08_lambda_functions.png`
- `docs/evidence/09_cloudformation_stack_outputs.png`

## 4. Kiểm Soát Chi Phí

### Ảnh Chụp Màn Hình Chi Phí

| Thời gian | Ảnh chụp màn hình | Ghi chú |
|---|---|---|
| Cuối Ngày 1 - 2026-05-28 | `docs/evidence/cost_day1_eod.png` | TODO: tổng cộng, các dịch vụ tốn kém nhất |
| Cuối Ngày 2 - 2026-05-29 | `docs/evidence/cost_day2_eod.png` | TODO: tổng cộng, các dịch vụ tốn kém nhất |
| Sáng ngày Demo - 2026-05-30 | `docs/evidence/cost_demo_morning.png` | TODO: tổng trước khi demo |

### Các Yếu Tố Tốn Kém Nhất

| Hạng | Dịch vụ | Chi phí | Lý do xuất hiện |
|---|---:|---:|---|
| 1 | TODO: Bedrock / OpenSearch / VPC Endpoint | TODO | TODO |
| 2 | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO |

### Các Biện Pháp Kiểm Soát Chi Phí

- Minh chứng budget phải thể hiện đúng yêu cầu W7: cảnh báo `$80` và SNS email đã confirm. `template.yaml` hiện đã định nghĩa budget `$100` với threshold `80%`, tương ứng cảnh báo `$80`.
- Cost Guard Lambda có thể đóng băng concurrent capacity của backend Lambda và đính kèm `StudyBotCostDenyPolicy` nếu đạt tới ngưỡng ngân sách.
- Auto-fix Lambda theo dõi các sự kiện CloudTrail để phát hiện việc tạo EC2/RDS/OpenSearch không được phép và có thể xóa các tài nguyên tốn kém.
- Kiến trúc này tránh sử dụng NAT Gateway và dùng S3/DynamoDB gateway endpoints cộng với Bedrock interface endpoints.

Ảnh chụp màn hình bắt buộc:
- `docs/evidence/10_budget_alert.png` - Xác nhận AWS Budget và SNS subscription.
- `docs/evidence/11_cost_anomaly_detection.png` - Cost Anomaly Detection (Phát hiện chi phí bất thường) được bật.
- `docs/evidence/12_cost_guard_lambda.png` - Cost Guard Lambda và các biến môi trường.
- `docs/evidence/13_cost_explorer_by_service.png` - chi phí nhóm theo dịch vụ.

## 5. Bảo Mật

### Đặc Quyền Tối Thiểu IAM

Vai trò thực thi Lambda `studybot-lambda-role-G15` được giới hạn trong các tài nguyên ứng dụng:

- S3 read/write/list/delete chỉ dành cho bucket tài liệu và bucket flashcard.
- DynamoDB read/write/query/update/delete chỉ dành cho bảng StudyBot.
- Quyền Bedrock `InvokeModel`, `Retrieve`, và `RetrieveAndGenerate` cho việc sử dụng mô hình và knowledge-base.
- CloudWatch `PutMetricData` chỉ cho namespace `StudyBot`.
- Truy cập Lambda VPC và CloudWatch logging thông qua policy vai trò thực thi được quản lý.

### Bảo Mật Mạng

- Các hàm Lambda chạy trong StudyBot VPC private subnet.
- S3 và DynamoDB sử dụng gateway VPC endpoints.
- Bedrock runtime và Bedrock agent runtime sử dụng interface VPC endpoints.
- VPC endpoint security group chỉ chấp nhận kết nối HTTPS từ Lambda security group.
- Không có database nào mở công khai ra Internet.

### Bảo Mật Đối Tượng

- Các bucket S3 phải được bật Block Public Access (Chặn truy cập công khai).
- CloudFront phân phối các asset frontend; quyền truy cập S3 trực tiếp công khai phải được chặn.
- Tài liệu tải lên và các tạo tác học tập sinh ra được lưu trữ trong S3 dưới các tiền tố (prefix) giới hạn.

Ảnh chụp màn hình bắt buộc:
- `docs/evidence/14_iam_lambda_role_policy.png`
- `docs/evidence/15_vpc_private_subnet.png`
- `docs/evidence/16_vpc_endpoints.png`
- `docs/evidence/17_s3_block_public_access.png`
- `docs/evidence/18_bedrock_model_access.png`

## 6. Giám Sát

CloudWatch được sử dụng cho log, số liệu (metrics), dashboard và cảnh báo (alarms).

Bằng chứng cần thu thập:

| Bằng chứng | Những gì cần thể hiện |
|---|---|
| `docs/evidence/19_cloudwatch_dashboard.png` | Dashboard `StudyBot-G15` hiển thị số lượt gọi/lỗi/thời lượng của Lambda và các request API Gateway. |
| `docs/evidence/20_alarm_query_errors.png` | Cảnh báo `StudyBot-G15-QueryErrors` ở trạng thái OK hoặc ALARM, không phải INSUFFICIENT_DATA. |
| `docs/evidence/21_alarm_upload_errors.png` | Cảnh báo `StudyBot-G15-UploadErrors` ở trạng thái OK hoặc ALARM. |
| `docs/evidence/22_log_insights_query.png` | Kết quả truy vấn Log Insights thực tế từ log Lambda. |
| `docs/evidence/23_custom_metrics.png` | Namespace `StudyBot`, ví dụ: `FlashcardGenerationLatency`, `FlashcardGenerationSuccess`, `SocraticQueryLatency`. |

Truy vấn Log Insights được đề xuất:

```sql
fields @timestamp, @message
| filter @message like /flashcard|query|evaluate|ERROR|WARN/
| sort @timestamp desc
| limit 50
```

## 6.5 Đo Lường và Quyết Định

### Quyết định 1: Sử dụng Claude 3.5 Sonnet cho chất lượng demo cuối, giữ Haiku là phương án rẻ hơn

**Các lựa chọn thay thế đã xem xét**

- Claude 3.5 Haiku: phương án rẻ hơn và phù hợp cho vòng dev; dùng lại Haiku nếu Cost Explorer cho thấy Bedrock trở thành cost driver lớn.
- Stub model chỉ chạy cục bộ: bị loại cho demo cuối cùng vì quy định yêu cầu gọi Bedrock thực tế từ ứng dụng, không phải từ console hay đầu ra mô phỏng.
- Các mô hình lớn hơn/dự phòng được liệt kê trong `AI_MODEL_FALLBACKS`: chỉ giữ làm dự phòng, không phải đường dẫn thông thường, để kiểm soát chi phí.

**Đo lường**

- TODO: Chạy 5 prompt đại diện trên cấu hình Sonnet đã deploy và ghi lại độ trễ trung bình: `___ ms`.
- TODO: Ghi lại tỷ lệ câu trả lời chấp nhận được trên 5 câu hỏi học tập: `___/5`.
- Tham khảo giá từ ước tính chi phí W7: Haiku `$1.00 / 1 triệu token đầu vào` và `$5.00 / 1 triệu token đầu ra`; Sonnet cao hơn khoảng 3 lần, nên lựa chọn này phải được chứng minh bằng chất lượng câu trả lời.

**Bằng chứng**

- `docs/evidence/24_bedrock_model_answer.png`
- `docs/evidence/25_model_cost_comparison.png`
- Metric tùy chỉnh CloudWatch: `SocraticQueryLatency`.

**Đánh đổi được chấp nhận**

- Sonnet tốn chi phí cao hơn Haiku. Chúng tôi chỉ chấp nhận điều này cho chất lượng demo cuối; nếu tổng chi phí tiến gần vùng cảnh báo, đổi lại Haiku trong `samconfig.toml` và cập nhật evidence.

### Quyết định 2: Sử dụng DynamoDB để duy trì trạng thái học tập thay vì RDS

**Các lựa chọn thay thế đã xem xét**

- RDS PostgreSQL: bị loại vì demo cần metadata người dùng/tài liệu/truy vấn/bài kiểm tra đơn giản, không cần các thao tác join quan hệ hay báo cáo SQL.
- SQLite: bị loại cho luồng triển khai thực tế vì truy cập đồng thời của Lambda và việc duy trì dữ liệu qua các lần triển khai yếu hơn.
- Trạng thái JSON chỉ dùng S3: bị loại đối với danh sách tài liệu/lịch sử truy vấn vì việc đọc và cập nhật cấp item dễ dàng hơn trên DynamoDB.

**Đo lường**

- TODO: Số lượng bản ghi được duy trì sau khi chạy luồng tải lên/truy vấn/bài kiểm tra cho demo: `___ items`.
- TODO: Chi phí đọc/ghi DynamoDB từ Cost Explorer: `$___`.
- Chi phí tham khảo của DynamoDB on-demand là cực nhỏ đối với lưu lượng demo: khoảng hàng trăm lượt đọc/ghi thì chi phí thấp hơn rất nhiều so với 1 đô la.

**Bằng chứng**

- `docs/evidence/26_dynamodb_items.png`
- `docs/evidence/27_docs_list_persistence.png`
- `docs/evidence/28_fresh_session_persistence.png`

**Đánh đổi được chấp nhận**

- DynamoDB ít thuận tiện hơn SQL trong phân tích quan hệ đột xuất. Chúng tôi chấp nhận điều đó vì mẫu truy cập cốt lõi của StudyBot là "lấy tài liệu của người dùng này, các truy vấn gần đây, flashcard, và trạng thái bài kiểm tra".

### Quyết định 3: Sử dụng VPC endpoints và tránh NAT Gateway

**Các lựa chọn thay thế đã xem xét**

- NAT Gateway: bị loại vì nó làm tăng chi phí cố định hàng giờ cộng với chi phí xử lý dữ liệu ngay cả khi ứng dụng đang rảnh.
- Public Lambda không có VPC: bị loại vì tiêu chí chấm điểm yêu cầu bằng chứng nền tảng mạng và trạng thái tài nguyên riêng tư (private).
- Một private subnet duy nhất với chỉ các endpoint cần thiết: được chọn vì tính đơn giản trong hackathon và kỷ luật chi phí.

**Đo lường**

- TODO: Số lượng NAT Gateway trong VPC: `0`.
- TODO: Số lượng VPC endpoints: S3 gateway `1`, DynamoDB gateway `1`, Bedrock interface `2`.
- Tham khảo ước tính chi phí: một Bedrock interface endpoint trong 48 giờ ở Singapore khoảng `$0.62`; NAT Gateway cho 48 giờ khoảng `$2.83` trước phí xử lý dữ liệu.

**Bằng chứng**

- `docs/evidence/16_vpc_endpoints.png`
- `docs/evidence/29_no_nat_gateway.png`
- `docs/evidence/30_private_route_table.png`

**Đánh đổi được chấp nhận**

- Interface endpoints đòi hỏi công sức cấu hình và mỗi endpoint dịch vụ bổ sung đều tốn phí hàng giờ. Chúng tôi chấp nhận điều này vì ứng dụng chủ yếu gọi các dịch vụ AWS và không cần đường egress rộng ra Internet.

### Quyết định 4: Thêm endpoint đo lường chất lượng truy xuất

**Các lựa chọn thay thế đã xem xét**

- Tự xem xét câu trả lời AI bằng mắt: bị loại vì nó không tạo ra bằng chứng lặp lại được.
- Một framework đánh giá offline đầy đủ: bị loại vì nó quá nặng cho 48 giờ.
- Một endpoint `/docs/{doc_id}/evaluate` nhẹ nhàng: được chọn vì nó cho biết Precision@1/3/5 và MRR trực tiếp ngay trong UI sản phẩm.

**Đo lường**

- TODO: Precision@1 = `___`.
- TODO: Precision@3 = `___`.
- TODO: Precision@5 = `___`.
- TODO: MRR = `___`.

**Bằng chứng**

- `docs/evidence/31_rag_evaluation_metrics.png`
- `tests/test_evaluation.py`
- Bảng UI metrics trong `frontend/index.html`.

**Đánh đổi được chấp nhận**

- Quá trình benchmark sử dụng một tập câu hỏi thăm dò nhỏ, do đó đây không phải là một đánh giá học thuật toàn diện. Nó vẫn tốt hơn những tuyên bố không đo lường được và đủ để giải thích hành vi chunking/truy xuất trong quá trình hỏi đáp (Q&A).

## 7. Bài Học Rút Ra

TODO: Thay thế phần này bằng phiên bản cuối cùng dài 200 từ sau buổi demo.

Bản nháp:

StudyBot đã dạy chúng tôi rằng phần khó nhất của "trò chuyện với PDF" không phải là tải file lên; mà là làm cho câu trả lời bám sát nội dung, có thể đo lường được, và đủ rẻ để chạy liên tục. Kiến trúc serverless cho phép chúng tôi di chuyển nhanh chóng: S3 xử lý tài liệu, DynamoDB quản lý trạng thái người dùng, Lambda xử lý logic sản phẩm, và Bedrock cung cấp lớp AI. Quyết định kỹ thuật tốt nhất là thêm các tính năng định hướng bằng chứng từ sớm, đặc biệt là đánh giá RAG và các số liệu CloudWatch, vì chúng cung cấp cho chúng tôi những con số thay vì những tuyên bố mơ hồ.

Trường hợp thất bại chính mà chúng tôi nhận thấy là chất lượng truy xuất: nếu kích thước đoạn (chunking) quá lớn, câu trả lời có thể trích dẫn một phần bao quát thay vì một điểm học tập chính xác; nếu quá nhỏ, mô hình sẽ mất ngữ cảnh. Chúng tôi đã giảm thiểu điều này bằng cách đưa ra các tùy chọn chunking theo cấu trúc, ngữ nghĩa và cố định, đồng thời đo lường Precision@K/MRR trên các câu hỏi thăm dò.

Nếu có thêm một sprint nữa, chúng tôi sẽ cải thiện danh tính người dùng thay vì chỉ dùng `X-User-Id` để demo, thêm các trích dẫn rõ ràng hơn theo từng tài liệu trong UI, và benchmark nhiều lựa chọn mô hình hơn. Các công cụ thực tế như NotebookLM và Khanmigo cho thấy trải nghiệm người dùng học tập cần sự tin tưởng: các trích dẫn, tính nhất quán (persistence), và các chế độ báo lỗi minh bạch quan trọng không kém gì chất lượng văn bản sinh ra.

## 8. Kế Hoạch Dọn Dẹp (Teardown Plan)

Thời hạn dọn dẹp: Cuối ngày Chủ nhật 2026-06-01.

Trình tự dọn dẹp:

1. Lưu ảnh chụp màn hình Cost Explorer cuối cùng và các bằng chứng demo.
2. Làm trống S3 bucket của frontend và các bucket chứa tài liệu/flashcard.
3. Xóa SAM stack:

```bash
sam delete --stack-name sam-app --region ap-southeast-1
```

4. Xóa hoặc xác minh đã xóa bất kỳ Bedrock Knowledge Base/vector store nào được tạo riêng.
5. Xóa CloudFront distribution sau khi vô hiệu hóa nó nếu nó được tạo ngoài SAM.
6. Xóa bất kỳ bộ sưu tập OpenSearch Serverless nào nếu có sử dụng.
7. Xóa bất kỳ VPC endpoints, security groups, subnets, và VPC nào còn sót lại nếu chúng không thuộc quyền quản lý của stack.
8. Xóa các tài nguyên Budget/SNS nếu không có ý định giữ lại.
9. Chạy Cost Explorer sau khi dọn dẹp và chụp ảnh màn hình xác nhận.

Ảnh chụp màn hình bắt buộc khi dọn dẹp:
- `docs/evidence/32_stack_deleted.png`
- `docs/evidence/33_s3_buckets_empty_or_deleted.png`
- `docs/evidence/34_bedrock_kb_deleted_or_final_state.png`
- `docs/evidence/35_cost_after_teardown.png`

## Danh Sách Kiểm Tra Chụp Ảnh Màn Hình

Sử dụng danh sách này trong khi xây dựng và demo. Đặt tất cả hình ảnh vào thư mục `docs/evidence/`.

| File | Ảnh chụp màn hình cần lấy | Vị trí AWS/UI |
|---|---|---|
| `01_live_url_loaded.png` | Ứng dụng HTTPS công khai được tải | Trình duyệt |
| `03_upload_flow.png` | Tải lên thành công | StudyBot UI |
| `04_ai_answer_with_context.png` | Câu trả lời Q&A từ tài liệu đã tải | StudyBot UI |
| `05_flashcards_or_quiz.png` | Flashcard hoặc bài kiểm tra được tạo | StudyBot UI |
| `06_architecture_diagram.png` | Sơ đồ kiến trúc cuối cùng đã triển khai | Bản xuất sơ đồ |
| `07_api_gateway_routes.png` | Các route API | API Gateway console |
| `08_lambda_functions.png` | 3 Lambda backend | Lambda console |
| `09_cloudformation_stack_outputs.png` | SAM/CFN outputs | CloudFormation console |
| `10_budget_alert.png` | Xác nhận cảnh báo ngân sách và SNS | AWS Budgets/SNS |
| `11_cost_anomaly_detection.png` | Phát hiện chi phí bất thường được bật | Cost Management |
| `13_cost_explorer_by_service.png` | Chi phí theo dịch vụ | Cost Explorer |
| `14_iam_lambda_role_policy.png` | IAM role inline policy | IAM console |
| `15_vpc_private_subnet.png` | Private subnet | VPC console |
| `16_vpc_endpoints.png` | S3/DynamoDB/Bedrock endpoints | VPC console |
| `17_s3_block_public_access.png` | Block Public Access (Chặn Truy cập Công khai) | S3 console |
| `18_bedrock_model_access.png` | Quyền truy cập mô hình được bật | Bedrock console |
| `19_cloudwatch_dashboard.png` | Dashboard có dữ liệu | CloudWatch |
| `20_alarm_query_errors.png` | Query alarm OK/ALARM | CloudWatch Alarms |
| `22_log_insights_query.png` | Kết quả Log Insights query | CloudWatch Logs Insights |
| `23_custom_metrics.png` | Các số liệu tùy chỉnh StudyBot | CloudWatch Metrics |
| `26_dynamodb_items.png` | Trạng thái ứng dụng được lưu trữ | DynamoDB console |
| `28_fresh_session_persistence.png` | Dữ liệu vẫn hiển thị ở session mới | Trình duyệt |
| `29_no_nat_gateway.png` | Số lượng NAT Gateway là 0 | Trang VPC NAT Gateway |
| `31_rag_evaluation_metrics.png` | Bảng Precision@K/MRR | StudyBot UI |
| `36_s3_uploaded_document.png` | Object tài liệu đã upload | S3 console |
| `37_s3_quiz_json.png` | Object JSON quiz đã lưu | S3 console |
| `32_stack_deleted.png` | Stack đã bị xóa sau demo | CloudFormation |
| `35_cost_after_teardown.png` | Chi phí cuối cùng sau khi dọn dẹp | Cost Explorer |

## Phu Luc - Luong Xu Ly End-to-End

Day la phan bo sung de trainer thay ro cach he thong xu ly request that, khong chi la danh sach dich vu.

### Luong 1 - Mo ung dung cong khai

1. Hoc sinh mo URL HTTPS cua CloudFront.
2. CloudFront phuc vu HTML/CSS/JS tu S3 frontend bucket.
3. Trinh duyet goi API Gateway bang API base URL da cau hinh.
4. API Gateway dieu huong cac request nhe nhu `/health`, `/docs/list`, va `/queries/recent` den Lambda `studybot-core`.

Minh chung can chup:
- `docs/evidence/01_live_url_loaded.png` - URL CloudFront dang mo tren browser.
- `docs/evidence/07_api_gateway_routes.png` - cac route API Gateway tro den Lambda.
- `docs/evidence/09_cloudformation_stack_outputs.png` - API URL va stack outputs sau khi deploy.

### Luong 2 - Upload va index tai lieu hoc tap

1. Hoc sinh upload PDF/TXT/slide export tu UI StudyBot.
2. Browser gui `POST /upload` den API Gateway kem `X-User-Id`.
3. API Gateway invoke Lambda `studybot-upload`.
4. Lambda trich xuat text va metadata cua tai lieu.
5. Lambda luu file goc va artifact da trich xuat vao S3.
6. Lambda luu metadata tai lieu theo user vao DynamoDB.
7. Neu Bedrock Knowledge Base da cau hinh, noi dung tai lieu duoc chuan bi cho retrieval/indexing; neu KB gap loi, fallback keyword/local vector van giu duoc happy path Q&A.
8. Lambda ghi log va metric vao CloudWatch.

Minh chung can chup:
- `docs/evidence/03_upload_flow.png` - upload thanh cong tren UI.
- `docs/evidence/36_s3_uploaded_document.png` - object tai lieu trong S3.
- `docs/evidence/26_dynamodb_items.png` - metadata tai lieu trong DynamoDB.
- `docs/evidence/22_log_insights_query.png` - log upload trong CloudWatch.

### Luong 3 - Hoi dap co grounding bang RAG

1. Hoc sinh dat cau hoi trong chat UI.
2. Browser gui `POST /query` den API Gateway.
3. API Gateway invoke Lambda `studybot-query`.
4. Lambda xac dinh user hien tai va tai lieu dang chon.
5. Lambda retrieve context lien quan tu Bedrock Knowledge Base hoac fallback local/vector path.
6. Lambda goi model Bedrock dang cau hinh trong `samconfig.toml` voi cau hoi va context da retrieve.
7. Lambda tra cau tra loi va context/citation ve browser.
8. Lambda luu recent query vao DynamoDB va publish latency metric nhu `SocraticQueryLatency`.

Minh chung can chup:
- `docs/evidence/04_ai_answer_with_context.png` - cau tra loi hien tren UI.
- `docs/evidence/24_bedrock_model_answer.png` - cau tra loi tu Bedrock that.
- `docs/evidence/23_custom_metrics.png` - custom metric `SocraticQueryLatency`.
- `docs/evidence/27_docs_list_persistence.png` - tai lieu/query cu van con hien thi.

### Luong 4 - Tao flashcards va quiz

1. Hoc sinh chon tai lieu va bam Generate AI / Generate Quiz.
2. Browser gui `POST /flashcards` hoac `POST /quiz` den API Gateway.
3. API Gateway invoke Lambda `studybot-query`.
4. Lambda tao prompt tu context cua tai lieu dang chon va yeu cau Bedrock tra ve JSON co cau truc.
5. Lambda validate/parse JSON sinh ra.
6. Voi quiz, Lambda luu JSON vao flashcard S3 bucket theo key user va document.
7. Voi flashcards, backend hien tai tra JSON ve UI va publish CloudWatch metrics; khong claim S3 persistence cho flashcards neu chua implement save/load.
8. UI render bo hoc tap da sinh; `GET /quiz/{doc_id}` co the load lai quiz da luu.

Minh chung can chup:
- `docs/evidence/05_flashcards_or_quiz.png` - flashcard/quiz hien tren UI.
- `docs/evidence/37_s3_quiz_json.png` - JSON quiz da luu trong S3.
- `docs/evidence/23_custom_metrics.png` - `FlashcardGenerationLatency` hoac `FlashcardGenerationSuccess`.

### Luong 5 - Quay lai session moi va kiem tra persistence

1. Hoc sinh refresh browser hoac mo session moi.
2. Browser goi `/docs/list`, `/queries/recent`, va endpoint quiz da luu.
3. Lambda core/query doc user state tu DynamoDB va quiz JSON tu S3.
4. UI hien thi tai lieu da upload, recent query, va quiz da luu. Flashcards hien la generated-on-demand tru khi save/load flashcard S3 duoc implement.

Minh chung can chup:
- `docs/evidence/28_fresh_session_persistence.png` - session moi van thay du lieu cu.
- `docs/evidence/26_dynamodb_items.png` - record user/document da persist.
- `docs/evidence/37_s3_quiz_json.png` - artifact quiz da persist trong S3.
