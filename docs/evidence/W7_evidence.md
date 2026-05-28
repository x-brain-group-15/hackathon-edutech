# W7 Evidence Pack - StudyBot / AI Study Buddy

> Status: draft for final submission. Replace every `TODO` with the real deployed value and add screenshots under ``.

## 1. Cover

| Field | Value |
|---|---|
| Group | TODO: G15 |
| Members | TODO: member names |
| Domain | EduTech - AI Study Buddy |
| Use case | Upload lecture PDFs/slides/text notes, then ask questions, generate flashcards/quizzes, and continue studying from saved state. |
| Live public URL | TODO: CloudFront HTTPS URL, or final HTTPS frontend URL used by trainer |
| API URL | `https://1lse4odraj.execute-api.ap-southeast-1.amazonaws.com` or TODO: final API Gateway URL |
| GitHub repo | TODO: public repo URL |
| AWS region | `ap-southeast-1` |
| Total spend | TODO: USD from final Cost Explorer screenshot |
| Demo video | TODO: `docs/demo.mp4` or YouTube unlisted link |

Required screenshots for this section:
- `01_live_url_loaded.png` - trainer-visible HTTPS app loaded in browser.
- `02_repo_readme.png` - public GitHub repo with README, architecture, setup, teardown.

## 2. Pitch and Vision

StudyBot helps students turn lecture materials into active study assets. A learner uploads a PDF, slide export, or text note, then receives grounded Q&A, flashcards, quizzes, Cornell notes, and retrieval-quality feedback from the same learning material.

Target users are university students, self-learners, and exam-prep learners who already have notes but lose time converting them into revision workflows. The project matters because the useful product is not just "chat with PDF"; it is a study loop: upload, ask, generate, review, and return later with state preserved.

Required screenshots:
- `03_upload_flow.png` - file selected/uploaded successfully.
- `04_ai_answer_with_context.png` - Q&A answer generated from uploaded document.
- `05_flashcards_or_quiz.png` - generated flashcards/quiz visible in UI.

## 3. Architecture

### Final Diagram

Final architecture diagram: TODO: add image at `architecture.png`.

The deployed architecture is serverless:

| Capability | Service used | Evidence |
|---|---|---|
| 1. Public user interface | CloudFront + S3 static frontend, deployed outside the SAM backend stack | TODO: CloudFront distribution screenshot |
| 2. Application compute | API Gateway HTTP API + AWS Lambda (`studybot-query`, `studybot-upload`, `studybot-core`) | TODO: Lambda/API Gateway screenshots |
| 3. AI / ML feature | Amazon Bedrock Claude Sonnet in current `samconfig.toml` + Bedrock Knowledge Base / direct InvokeModel fallback | TODO: Bedrock model access + UI result |
| 4. Data persistence | DynamoDB user/document/query state; S3 JSON for saved quizzes; uploaded documents in S3 | TODO: DynamoDB item + S3 object screenshots |
| 5. Object storage | S3 document bucket and flashcard/quiz bucket | TODO: S3 bucket object list |
| 6. Network foundation | VPC, private subnet, Lambda SG, S3/DynamoDB gateway endpoints, Bedrock interface endpoints | TODO: VPC/subnet/endpoint screenshots |
| 7. Identity & access | IAM least-privilege Lambda execution role; demo user via `X-User-Id` | TODO: IAM policy screenshot |

### Service Decisions

| Decision | Choice | Reason |
|---|---|---|
| Compute | Lambda split into query/upload/core functions | Keeps idle cost near zero and lets heavy AI/upload routes have longer timeout without over-sizing health/list routes. |
| API entry | API Gateway HTTP API | Cheaper and simpler than REST API for this request/response app. |
| Frontend | S3 + CloudFront | Public HTTPS, low cost, no server to manage. |
| Database | DynamoDB on-demand | Access patterns are key-value/user-document state; no relational joins needed for demo. |
| Object storage | S3 | PDFs, extracted content, and saved quiz JSON are blob/document data. |
| AI model | Claude 3.5 Sonnet in current deployment config | Higher quality for final demo answers; if cost becomes the priority, switch `AiModelId` back to Haiku and update this evidence. |
| RAG | Bedrock Knowledge Base, with local keyword fallback in code | Better grounded answers when KB is ready; fallback keeps demo path alive if KB ingestion has issues. |
| Network | Private Lambda subnet + VPC endpoints, no NAT Gateway | S3/DynamoDB gateway endpoints are free; Bedrock endpoints avoid NAT fixed cost. |
| Observability | CloudWatch dashboard, alarms, logs, custom metrics | Gives operational proof and supports optional Full Observability. |
| IaC | AWS SAM / CloudFormation in `template.yaml` | Reproducible deploy and easier teardown through stack deletion. |

### Trade-offs

1. Lambda vs EC2/ECS: chose Lambda for 48-hour speed and low idle cost. Accepted cold starts and request timeout limits.
2. DynamoDB vs RDS: chose DynamoDB because user state and document metadata are simple access patterns. Accepted weaker ad-hoc querying.
3. Bedrock KB vs direct InvokeModel: chose KB for grounded retrieval. Kept direct/local fallback because KB setup and ingestion can be the riskiest demo dependency.

### Upload PDF and Content Extraction Flow

PDF upload is the main entry point for StudyBot. A learner selects a PDF/TXT/MD file in the frontend, the browser calls `POST /upload` through API Gateway, Lambda `studybot-upload` receives the file, stores the original object, extracts learning content, ingests text into retrieval, saves document metadata under the current `user_id`, and returns a `doc_id` to the UI.

Real flow:

```text
Frontend selects PDF
-> POST /upload with X-User-Id
-> Lambda stores original file in S3/local storage
-> If PDF: run hybrid PDF extraction
-> Store extracted_text.txt and extracted image/chart assets
-> Ingest text into vector store / retrieval fallback
-> Save document metadata into userstore/DynamoDB
-> Emit DOCUMENT_UPLOAD and PROCESS_STEP logs to CloudWatch
-> Return doc_id, location, chars_extracted, extraction metadata to frontend
```

**Hybrid PDF extraction strategy**

The team does not OCR/Textract the whole PDF by default because many exported slide PDFs already contain a readable text layer. The current pipeline:

1. Reads page text layers with `pypdf`.
2. Counts image objects on each page to detect visual-heavy slides.
3. Extracts image/chart assets through the same storage adapter as the original file.
4. Skips images smaller than `8KB` to avoid storing low-value logos/icons/masks.
5. Deduplicates images with SHA-256 across the whole document.
6. Ingests text-layer content directly when a page has enough text.
7. Marks text-poor pages with images as `needs_ocr_or_textract`.
8. Returns normalized text, page-level metadata, and S3/local URIs for visual assets.

Strategy name in response metadata:

```text
hybrid_text_layer_plus_image_assets_then_page_level_ocr
```

**Stored object layout**

Example for `user_id = test-user-001`, any generated `doc_id`, and `W6_Operations.pdf`:

```text
Original PDF:
test-user-001/{doc_id}/W6_Operations.pdf

Bedrock KB metadata:
test-user-001/{doc_id}/W6_Operations.pdf.metadata.json

Extracted plain text:
test-user-001/{doc_id}/extracted_text.txt

Filtered image/chart assets:
test-user-001/{doc_id}/extracted-assets/page_001_image_001.png
```

With `STORAGE_BACKEND=local`, locations are returned as `file://...`. With `STORAGE_BACKEND=s3`, locations are returned as `s3://bucket/...`.

**Upload response metadata**

```json
{
  "doc_id": "generated-doc-id",
  "filename": "W6_Operations.pdf",
  "size": 7497312,
  "chars_extracted": 5671,
  "location": "s3://studybot-uploads/test-user-001/generated-doc-id/W6_Operations.pdf",
  "extraction": {
    "page_count": 20,
    "chars_extracted": 5671,
    "images_extracted": 27,
    "pages_requiring_ocr": [20],
    "pages_with_images_or_charts": [1, 2, 3],
    "pages_with_table_like_content": [],
    "strategy": "hybrid_text_layer_plus_image_assets_then_page_level_ocr",
    "asset_prefix": "test-user-001/generated-doc-id/extracted-assets"
  }
}
```

**Test evidence**

| Test file | Page count | Chars extracted | Images extracted | Pages requiring OCR/Textract | Conclusion |
|---|---:|---:|---:|---|---|
| `tests/W6_Operations_Hardening_&_Cost-Aware_Cloud_-_Nhóm_15.pptx.pdf` | 20 | 5671 | 27 | `[20]` | Visual-heavy slide PDF; only page 20 needs OCR/Textract. |
| `tests/SCA_KLTN_Nhom30_3.ProjectUserStrory.pdf` | 25 | about 36,000 | 2 | `[]` | Clean text-layer PDF; no OCR needed. |

For the W6 file, image filtering reduced `83` raw image objects to `43` after size filtering, then `27` after size filtering plus deduplication. This reduces noisy stored assets while preserving useful slide visuals for downstream retrieval.

**Repo evidence**

- `docs/pdf_extraction.md` - hybrid extraction strategy, output shape, trade-off, and test results.
- `src/pdf_extractor.py` - implementation for PDF parsing, `8KB` image filtering, SHA-256 deduplication, and OCR/Textract flags.
- `src/handlers.py` - upload integration: original file, `.metadata.json`, `extracted_text.txt`, extracted assets, vector ingest, and user metadata.
- `lambda_upload.py` - Lambda/FastAPI `POST /upload` route.
- `tests/test_pdf_extractor.py` - metadata test for a text-poor PDF.

### End-to-End Processing Flow

This is the real application flow the demo should prove, not only a service list.

#### Flow 1 - Open the public app

1. Student opens the final HTTPS frontend URL, expected to be CloudFront if the separate frontend deployment is active.
2. CloudFront serves static HTML/CSS/JS from the S3 frontend bucket.
3. The browser calls API Gateway using the configured API base URL.
4. API Gateway routes lightweight requests such as `/health`, `/docs/list`, and `/queries/recent` to `studybot-core`.

Evidence to capture:
- `01_live_url_loaded.png` - CloudFront URL in browser.
- `07_api_gateway_routes.png` - API Gateway routes mapped to Lambda.
- `09_cloudformation_stack_outputs.png` - deployed API URL and stack outputs.

#### Flow 2 - Upload and index a learning document

1. Student uploads a PDF/TXT/slide export from the StudyBot UI.
2. Browser sends `POST /upload` to API Gateway with `X-User-Id`.
3. API Gateway invokes `studybot-upload`.
4. Lambda extracts text and document metadata.
5. Lambda stores the original file and extracted artifacts in S3.
6. Lambda stores document metadata under the user's state in DynamoDB.
7. If Bedrock Knowledge Base is configured, the document content is prepared for retrieval/indexing; otherwise the local keyword retrieval fallback can still support demo Q&A.
8. Lambda writes logs and metrics to CloudWatch.

For PDFs, Lambda does not OCR the entire file upfront. It uses `pypdf` for the text layer first, extracts image/chart assets to `extracted-assets`, skips images under `8KB`, deduplicates images with SHA-256, and marks only text-poor visual pages as `needs_ocr_or_textract`. The W6 test showed 20 pages, 5671 characters, 27 image assets after filtering/deduplication, and only page 20 requiring OCR/Textract.

Evidence to capture:
- `03_upload_flow.png` - upload success in UI.
- `36_s3_uploaded_document.png` - uploaded object in S3.
- `26_dynamodb_items.png` - document metadata in DynamoDB.
- `22_log_insights_query.png` - upload log lines in CloudWatch.

#### Flow 3 - Ask a grounded question with RAG

1. Student asks a question in the chat UI.
2. Browser sends `POST /query` to API Gateway.
3. API Gateway invokes `studybot-query`.
4. Lambda identifies the current user and selected document.
5. Lambda retrieves relevant context from Bedrock Knowledge Base or the fallback local/vector path.
6. Lambda calls the configured Bedrock model from `samconfig.toml` with the question and retrieved context.
7. Lambda returns the answer and supporting context/citations to the browser.
8. Lambda stores recent query state in DynamoDB and publishes latency metrics such as `SocraticQueryLatency`.

Evidence to capture:
- `04_ai_answer_with_context.png` - answer visible in UI.
- `24_bedrock_model_answer.png` - real Bedrock-backed answer.
- `23_custom_metrics.png` - `SocraticQueryLatency` custom metric.
- `27_docs_list_persistence.png` - prior document/query still visible.

#### Flow 4 - Generate flashcards and quizzes

1. Student chooses a selected document and clicks Generate AI / Generate Quiz.
2. Browser sends `POST /flashcards` or `POST /quiz` to API Gateway.
3. API Gateway invokes `studybot-query`.
4. Lambda builds the prompt from selected document context and asks Bedrock to return structured JSON.
5. Lambda validates/parses the generated JSON.
6. For quizzes, Lambda stores generated JSON in the flashcard S3 bucket, keyed by user and document.
7. For flashcards, current backend returns generated JSON and publishes CloudWatch metrics; do not claim S3 persistence unless the flashcard S3 save/load feature is implemented.
8. UI renders the generated study set; a later `GET /quiz/{doc_id}` can reload saved quiz state.

Evidence to capture:
- `05_flashcards_or_quiz.png` - generated study set in UI.
- `37_s3_quiz_json.png` - saved quiz JSON object in S3.
- `23_custom_metrics.png` - `FlashcardGenerationLatency` or `FlashcardGenerationSuccess`.

#### Flow 5 - Return later and verify persistence

1. Student refreshes the browser or opens a new session.
2. Browser calls `/docs/list`, `/queries/recent`, and saved quiz endpoints.
3. Core/query Lambda reads user state from DynamoDB and saved quiz JSON from S3.
4. UI shows previous uploaded documents, recent query state, and saved quizzes. Flashcards should be shown as generated-on-demand unless S3 flashcard persistence is completed.

Evidence to capture:
- `28_fresh_session_persistence.png` - fresh session still shows prior data.
- `26_dynamodb_items.png` - persisted document/user records.
- `37_s3_quiz_json.png` - persisted quiz artifact.

Required screenshots:
- `06_architecture_diagram.png`
- `07_api_gateway_routes.png`
- `08_lambda_functions.png`
- `09_cloudformation_stack_outputs.png`

## 4. Cost Discipline

### Cost Screenshots

| Time | Screenshot | Notes |
|---|---|---|
| Day 1 EOD - 2026-05-28 | `cost_day1_eod.png` | TODO: total, top services |
| Day 2 EOD - 2026-05-29 | `cost_day2_eod.png` | TODO: total, top services |
| Demo morning - 2026-05-30 | `cost_demo_morning.png` | TODO: final pre-demo total |

### Top Cost Drivers

| Rank | Service | Cost | Why it appears |
|---|---:|---:|---|
| 1 | TODO: Bedrock / OpenSearch / VPC Endpoint | TODO | TODO |
| 2 | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO |

### Cost Controls

- Budget evidence must show the W7-required alert at `$80` with confirmed SNS email. `template.yaml` now defines a `$100` monthly budget with an `80%` threshold, which maps to the required `$80` alert.
- Cost Guard Lambda can freeze backend Lambda reserved concurrency and attach `StudyBotCostDenyPolicy` if budget thresholds are reached.
- Auto-fix Lambda watches CloudTrail events for unauthorized EC2/RDS/OpenSearch creation and can delete costly resources.
- The architecture avoids NAT Gateway and uses S3/DynamoDB gateway endpoints plus Bedrock interface endpoints.

Required screenshots:
- `10_budget_alert.png` - AWS Budget and SNS subscription confirmed.
- `11_cost_anomaly_detection.png` - Cost Anomaly Detection enabled.
- `12_cost_guard_lambda.png` - Cost Guard Lambda and environment variables.
- `13_cost_explorer_by_service.png` - cost grouped by service.

## 5. Security

### IAM Least Privilege

The Lambda execution role `studybot-lambda-role-G15` is scoped to the app resources:

- S3 read/write/list/delete only for the document bucket and flashcard bucket.
- DynamoDB read/write/query/update/delete only for the StudyBot table.
- Bedrock `InvokeModel`, `Retrieve`, and `RetrieveAndGenerate` for model and knowledge-base use. Bedrock resource scope may include foundation models/inference profiles because model ARNs differ by provider and region.
- CloudWatch `PutMetricData` only for namespace `StudyBot`.
- Lambda VPC access and CloudWatch logging through managed execution role policy.

### Network Security

- Lambda functions run inside the StudyBot VPC private subnet.
- S3 and DynamoDB use gateway VPC endpoints.
- Bedrock runtime and Bedrock agent runtime use interface VPC endpoints.
- VPC endpoint security group accepts HTTPS only from the Lambda security group.
- No database is public-facing.

### Object Security

- S3 buckets should have Block Public Access enabled.
- CloudFront serves frontend assets; direct public S3 access should remain blocked.
- Uploaded documents and generated study artifacts are stored in S3 under scoped prefixes.

Required screenshots:
- `14_iam_lambda_role_policy.png`
- `15_vpc_private_subnet.png`
- `16_vpc_endpoints.png`
- `17_s3_block_public_access.png`
- `18_bedrock_model_access.png`

## 6. Monitoring

CloudWatch is used for logs, metrics, dashboarding, and alarms.

Evidence to capture:

| Evidence | What to show |
|---|---|
| `19_cloudwatch_dashboard.png` | Dashboard `StudyBot-G15` with Lambda invocations/errors/duration and API Gateway requests. |
| `20_alarm_query_errors.png` | Alarm `StudyBot-G15-QueryErrors` in OK or ALARM state, not INSUFFICIENT_DATA. |
| `21_alarm_upload_errors.png` | Alarm `StudyBot-G15-UploadErrors` in OK or ALARM state. |
| `22_log_insights_query.png` | Real Log Insights results from Lambda logs. |
| `23_custom_metrics.png` | Namespace `StudyBot`, e.g. `FlashcardGenerationLatency`, `FlashcardGenerationSuccess`, `SocraticQueryLatency`. |

Suggested Log Insights query:

```sql
fields @timestamp, @message
| filter @message like /flashcard|query|evaluate|ERROR|WARN/
| sort @timestamp desc
| limit 50
```

### 6.1 Structured Logging and CloudWatch Logs Insights

The team implemented structured JSON logging in Lambda with Python `logging` and `json.dumps(...)`. Helper functions `log_event()` and `log_step()` make each log record queryable in CloudWatch Logs Insights instead of relying on free-form text.

Log event types currently emitted:

- `DOCUMENT_UPLOAD`
- `UPLOAD_ERROR`
- `RAG_QUERY`
- `RAG_ERROR`
- `PROCESS_STEP`
- `EVALUATE_RESULT`
- `EVALUATE_ERROR`

**Logging code evidence**

![Structured logging helper](log_code.jpg)

This screenshot shows `log_event()` and `log_step()` emitting records with `event_type` plus metadata such as `operation`, `step`, `user_id`, `doc_id`, and `filename`.

**Log group evidence**

![CloudWatch log group](log_group.jpg)

The `/aws/lambda/studybot-api-G15` log group confirms real Lambda logs are collected by CloudWatch Logs. Retention is configured for 3 days to fit the hackathon demo and cost-control window.

**Structured JSON log evidence**

![Structured JSON log](json_log.jpg)

The sample log shows a `PROCESS_STEP` event from the upload flow with `operation: upload`, `step: upload_start`, `user_id`, `doc_id`, `filename`, and `size`.

### 6.2 Upload Monitoring Queries

CloudWatch Logs Insights queries monitor successful document uploads and upload failures.

**Successful uploads**

![Document upload Logs Insights](document_upload.jpg)

```sql
fields @timestamp, user_id, filename, size
| filter event_type = "DOCUMENT_UPLOAD"
| sort size desc
| limit 10
```

This query tracks uploaded documents, largest files, and real ingestion activity from the demo user.

**Upload errors**

![Upload error Logs Insights](document_upload_error.jpg)

```sql
fields @timestamp, user_id, filename, error_type, error_message
| filter event_type = "UPLOAD_ERROR"
| sort @timestamp desc
| limit 20
```

The evidence captures `NameError: name 'io' is not defined` for some PDF uploads. This is useful failure-mode evidence because it shows the team can debug ingestion failures, not only demonstrate the happy path.

### 6.3 RAG Usage, Latency, and Error Queries

**RAG query count by user**

![RAG query Logs Insights](rag_query.jpg)

```sql
fields @timestamp, user_id, question
| filter event_type = "RAG_QUERY"
| stats count(*) as total_queries by user_id
| sort total_queries desc
```

The result shows demo user `test-user-001` with `16` RAG queries, which measures feature adoption.

**RAG latency**

![RAG latency Logs Insights](rag_latency.jpg)

```sql
fields latency_ms
| filter event_type = "RAG_QUERY"
| stats avg(latency_ms) as avg_latency,
        max(latency_ms) as max_latency,
        min(latency_ms) as min_latency
```

Measured result: `avg_latency = 847.2 ms`, `max_latency = 1970 ms`, `min_latency = 373 ms`. These numbers prove the RAG feature is not only callable but also measured operationally.

**RAG errors**

![RAG error Logs Insights](rag_error.jpg)

```sql
fields @timestamp, user_id, question, error_type, error_message
| filter event_type = "RAG_ERROR"
| sort @timestamp desc
| limit 20
```

The result shows `ThrottlingException` from Bedrock `RetrieveAndGenerate` and one Converse error caused by too many tokens. This evidence documents quota/token failure modes for the demo.

### 6.4 Lambda Process Tracing

`PROCESS_STEP` logs trace Lambda execution step by step: upload, list docs, query received, Bedrock retrieval/generation, query history save, and request completion.

![Process step Logs Insights](process_step.jpg)

```sql
fields @timestamp, operation, step, user_id, doc_id, question
| filter event_type = "PROCESS_STEP"
| sort @timestamp desc
| limit 50
```

The results include steps such as `query_received`, `bedrock_retrieve_generate_start`, `bedrock_retrieve_generate_done`, `save_query_history_start`, and `save_query_history_done`, which helps locate where a request became slow or failed.

### 6.5 Retrieval Evaluation Metrics

The system logs retrieval evaluation results to measure RAG quality with Precision@K, Recall@K, and MRR.

**Evaluation result**

![Evaluate result Logs Insights](evaluate_result.jpg)

```sql
fields filename,
       strategy_used,
       precision_at_1,
       precision_at_3,
       precision_at_5,
       recall_at_1,
       recall_at_3,
       recall_at_5,
       mrr
| filter event_type = "EVALUATE_RESULT"
| sort mrr desc
```

Sample result:

| File | Strategy | Precision@1 | Precision@3 | Precision@5 | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `wiki_04_photosynthesis.txt` | fixed | 0.4 | 0.4667 | 0.4 | 0.4 | 0.6 | 0.8 | 0.55 |
| `Requirements_Checklist.pdf` | fixed | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

**Evaluation errors**

![Evaluate error Logs Insights](evaluate_error.jpg)

```sql
fields @timestamp, doc_id, error_type, error_message
| filter event_type = "EVALUATE_ERROR"
| sort @timestamp desc
```

The evaluation-error query returned 0 matched records, meaning no `EVALUATE_ERROR` was present in the captured evidence window.

## 6.6 Measurement and Decisions

### Decision 1: Use Claude 3.5 Sonnet for final demo quality, with Haiku as the lower-cost alternative

**Alternatives considered**

- Claude 3.5 Haiku: lower-cost alternative and good for development loops; use it if Cost Explorer shows Bedrock becoming a top cost driver.
- Local-only stub model: eliminated for final demo because the rules require real Bedrock calls from the app, not console or mock output.
- Larger/fallback models listed in `AI_MODEL_FALLBACKS`: kept only as fallback, not the normal path, to avoid uncontrolled cost.

**Measurement**

- TODO: Run 5 representative prompts on the deployed Sonnet config and record average latency: `___ ms`.
- TODO: Record acceptable answer rate on 5 study questions: `___/5`.
- Pricing reference from W7 cost estimate: Haiku `$1.00 / 1M input tokens` and `$5.00 / 1M output tokens`; Sonnet is about 3x higher, so this choice must be justified by answer quality.

**Evidence**

- `24_bedrock_model_answer.png`
- `25_model_cost_comparison.png`
- CloudWatch custom metric: `SocraticQueryLatency`.

**Trade-off accepted**

- Sonnet costs more than Haiku. We accept this only for final demo quality; if total cost approaches the warning zone, switch back to Haiku in `samconfig.toml` and update the evidence.

### Decision 2: Use DynamoDB for persistent study state instead of RDS

**Alternatives considered**

- RDS PostgreSQL: eliminated because the demo needs simple user/document/query/quiz metadata, not relational joins or SQL reporting.
- SQLite: eliminated for deployed production path because Lambda concurrent access and persistence across deployments are weaker.
- S3-only JSON state: eliminated for document list/query history because item-level reads and updates are easier in DynamoDB.

**Measurement**

- TODO: Number of persisted records after demo upload/query/quiz flow: `___ items`.
- TODO: DynamoDB read/write cost from Cost Explorer: `$___`.
- DynamoDB on-demand reference cost is tiny for demo traffic: approximately hundreds of reads/writes are far below one dollar.

**Evidence**

- `26_dynamodb_items.png`
- `27_docs_list_persistence.png`
- `28_fresh_session_persistence.png`

**Trade-off accepted**

- DynamoDB is less convenient for ad-hoc relational analysis than SQL. We accept that because StudyBot's core access pattern is "get this user's documents, recent queries, flashcards, and quiz state."

### Decision 3: Use VPC endpoints and avoid NAT Gateway

**Alternatives considered**

- NAT Gateway: eliminated because it adds fixed hourly cost plus data processing cost even when the app is idle.
- Public Lambda without VPC: eliminated because the rubric requires network-foundation evidence and private resource posture.
- One private subnet with only required endpoints: chosen for hackathon simplicity and cost discipline.

**Measurement**

- TODO: NAT Gateway count in VPC: `0`.
- TODO: VPC endpoints count: S3 gateway `1`, DynamoDB gateway `1`, Bedrock interface `2`.
- Cost estimate reference: one Bedrock interface endpoint for 48h in Singapore is about `$0.62`; NAT Gateway for 48h is about `$2.83` before data processing.

**Evidence**

- `16_vpc_endpoints.png`
- `29_no_nat_gateway.png`
- `30_private_route_table.png`

**Trade-off accepted**

- Interface endpoints add configuration work and each extra service endpoint has hourly cost. We accept this because the app mainly calls AWS services and does not need broad internet egress.

### Decision 4: Add retrieval-quality measurement endpoint

**Alternatives considered**

- Manual eyeballing of AI answers: eliminated because it does not produce repeatable evidence.
- Full offline evaluation framework: eliminated because it is too heavy for 48 hours.
- Lightweight `/docs/{doc_id}/evaluate`: chosen because it gives Precision@1/3/5 and MRR directly in the product UI.

**Measurement**

- TODO: Precision@1 = `___`.
- TODO: Precision@3 = `___`.
- TODO: Precision@5 = `___`.
- TODO: MRR = `___`.

**Evidence**

- `31_rag_evaluation_metrics.png`
- `tests/test_evaluation.py`
- UI metrics panel in `frontend/index.html`.

**Trade-off accepted**

- The benchmark uses a small probe set, so it is not a full academic evaluation. It is still better than unmeasured claims and is enough to explain chunking/retrieval behavior during Q&A.

## 7. Lessons Learned

TODO: Replace this with the final 200-word version after demo.

Draft:

StudyBot taught us that the hardest part of "chat with PDF" is not uploading the file; it is making the answer grounded, measurable, and cheap enough to run repeatedly. The serverless architecture let us move quickly: S3 handled documents, DynamoDB handled user state, Lambda handled the product logic, and Bedrock provided the AI layer. The best engineering decision was to add evidence-oriented features early, especially RAG evaluation and CloudWatch metrics, because they gave us numbers instead of vague claims.

The main failure case we found was retrieval quality: if chunking is too coarse, the answer can cite a broad section instead of the exact learning point; if it is too small, the model loses context. We mitigated this by exposing fixed, structural, and semantic chunking options and measuring Precision@K/MRR on probe questions.

If we had another sprint, we would improve user identity beyond a demo `X-User-Id`, add stronger per-document citations in the UI, and benchmark more model choices. Real-world tools like NotebookLM and Khanmigo show that study UX needs trust: citations, persistence, and transparent failure modes matter as much as generation quality.

## 8. Teardown Plan

Teardown deadline: Sunday 2026-06-01 EOD.

Ordered teardown:

1. Save final Cost Explorer screenshot and demo evidence.
2. Empty the frontend S3 bucket and document/flashcard buckets.
3. Delete the SAM stack configured in `samconfig.toml`:

```bash
sam delete --stack-name sam-app --region ap-southeast-1
```

4. Delete or verify deletion of any separately-created Bedrock Knowledge Base/vector store.
5. Delete or disable the CloudFront distribution after emptying the frontend S3 bucket if it was created outside SAM.
6. Delete any OpenSearch Serverless collection if used.
7. Delete any leftover VPC endpoints, security groups, subnets, and VPC if not owned by the stack.
8. Delete Budget/SNS resources if not retained intentionally.
9. Run Cost Explorer after teardown and capture confirmation.

Required teardown screenshots:
- `32_stack_deleted.png`
- `33_s3_buckets_empty_or_deleted.png`
- `34_bedrock_kb_deleted_or_final_state.png`
- `35_cost_after_teardown.png`

## Screenshot Capture Checklist

Use this checklist while building and demoing. Put all images in ``.

| File | Screenshot to capture | AWS/UI location |
|---|---|---|
| `01_live_url_loaded.png` | Public HTTPS app loads | Browser |
| `03_upload_flow.png` | Upload success | StudyBot UI |
| `docs/pdf_extraction.md` | Hybrid PDF extraction technical evidence | Repo docs |
| `src/pdf_extractor.py` | PDF extraction, image filtering, deduplication, OCR/Textract flags | Repo source |
| `src/handlers.py` | Upload integration into storage/vector/userstore | Repo source |
| `lambda_upload.py` | Lambda `POST /upload` route | Repo source |
| `tests/test_pdf_extractor.py` | Text-poor PDF metadata test | Repo tests |
| `04_ai_answer_with_context.png` | Q&A answer from uploaded doc | StudyBot UI |
| `05_flashcards_or_quiz.png` | Flashcard or quiz generated | StudyBot UI |
| `06_architecture_diagram.png` | Final deployed architecture | Diagram export |
| `07_api_gateway_routes.png` | API routes | API Gateway console |
| `08_lambda_functions.png` | 3 backend Lambdas | Lambda console |
| `09_cloudformation_stack_outputs.png` | SAM/CFN outputs | CloudFormation console |
| `10_budget_alert.png` | Budget alert and SNS confirmed | AWS Budgets/SNS |
| `11_cost_anomaly_detection.png` | Cost anomaly enabled | Cost Management |
| `13_cost_explorer_by_service.png` | Cost by service | Cost Explorer |
| `14_iam_lambda_role_policy.png` | IAM role inline policy | IAM console |
| `15_vpc_private_subnet.png` | Private subnet | VPC console |
| `16_vpc_endpoints.png` | S3/DynamoDB/Bedrock endpoints | VPC console |
| `17_s3_block_public_access.png` | Block Public Access | S3 console |
| `18_bedrock_model_access.png` | Model access enabled | Bedrock console |
| `19_cloudwatch_dashboard.png` | Dashboard with data | CloudWatch |
| `20_alarm_query_errors.png` | Query alarm OK/ALARM | CloudWatch Alarms |
| `22_log_insights_query.png` | Log Insights query results | CloudWatch Logs Insights |
| `23_custom_metrics.png` | StudyBot custom metrics | CloudWatch Metrics |
| `log_code.jpg` | Structured logging code: `log_event()` / `log_step()` | Lambda source code |
| `log_group.jpg` | Log group `/aws/lambda/studybot-api-G15` | CloudWatch Logs |
| `json_log.jpg` | Real JSON log with `event_type`, `user_id`, `doc_id` | CloudWatch Logs |
| `document_upload.jpg` | `DOCUMENT_UPLOAD` query | CloudWatch Logs Insights |
| `document_upload_error.jpg` | `UPLOAD_ERROR` query | CloudWatch Logs Insights |
| `rag_query.jpg` | `RAG_QUERY` count by user | CloudWatch Logs Insights |
| `rag_latency.jpg` | RAG average/max/min latency query | CloudWatch Logs Insights |
| `rag_error.jpg` | `RAG_ERROR` query | CloudWatch Logs Insights |
| `process_step.jpg` | Lambda `PROCESS_STEP` trace query | CloudWatch Logs Insights |
| `evaluate_result.jpg` | Precision@K/Recall@K/MRR query | CloudWatch Logs Insights |
| `evaluate_error.jpg` | `EVALUATE_ERROR` query with no errors | CloudWatch Logs Insights |
| `26_dynamodb_items.png` | Persisted app state | DynamoDB console |
| `28_fresh_session_persistence.png` | Data still visible in fresh session | Browser |
| `29_no_nat_gateway.png` | NAT Gateway count is zero | VPC NAT Gateway page |
| `31_rag_evaluation_metrics.png` | Precision@K/MRR panel | StudyBot UI |
| `36_s3_uploaded_document.png` | Uploaded document object | S3 console |
| `37_s3_quiz_json.png` | Saved quiz JSON object | S3 console |
| `32_stack_deleted.png` | Stack deleted after demo | CloudFormation |
| `35_cost_after_teardown.png` | Final cost after teardown | Cost Explorer |
