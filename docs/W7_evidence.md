# W7 Evidence Pack - StudyBot / AI Study Buddy

> Status: draft for final submission. Replace every `TODO` with the real deployed value and add screenshots under `docs/evidence/`.

## 1. Cover

| Field | Value |
|---|---|
| Group | TODO: G15 |
| Members | TODO: member names |
| Domain | EduTech - AI Study Buddy |
| Use case | Upload lecture PDFs/slides/text notes, then ask questions, generate flashcards/quizzes, and continue studying from saved state. |
| Live public URL | TODO: CloudFront HTTPS URL |
| API URL | `https://1lse4odraj.execute-api.ap-southeast-1.amazonaws.com` or TODO: final API Gateway URL |
| GitHub repo | TODO: public repo URL |
| AWS region | `ap-southeast-1` |
| Total spend | TODO: USD from final Cost Explorer screenshot |
| Demo video | TODO: `docs/demo.mp4` or YouTube unlisted link |

Required screenshots for this section:
- `docs/evidence/01_live_url_loaded.png` - trainer-visible HTTPS app loaded in browser.
- `docs/evidence/02_repo_readme.png` - public GitHub repo with README, architecture, setup, teardown.

## 2. Pitch and Vision

StudyBot helps students turn lecture materials into active study assets. A learner uploads a PDF, slide export, or text note, then receives grounded Q&A, flashcards, quizzes, Cornell notes, and retrieval-quality feedback from the same learning material.

Target users are university students, self-learners, and exam-prep learners who already have notes but lose time converting them into revision workflows. The project matters because the useful product is not just "chat with PDF"; it is a study loop: upload, ask, generate, review, and return later with state preserved.

Required screenshots:
- `docs/evidence/03_upload_flow.png` - file selected/uploaded successfully.
- `docs/evidence/04_ai_answer_with_context.png` - Q&A answer generated from uploaded document.
- `docs/evidence/05_flashcards_or_quiz.png` - generated flashcards/quiz visible in UI.

## 3. Architecture

### Final Diagram

Final architecture diagram: TODO: add image at `docs/evidence/architecture.png`.

The deployed architecture is serverless:

| Capability | Service used | Evidence |
|---|---|---|
| 1. Public user interface | CloudFront + S3 static frontend | TODO: CloudFront distribution screenshot |
| 2. Application compute | API Gateway HTTP API + AWS Lambda (`studybot-query`, `studybot-upload`, `studybot-core`) | TODO: Lambda/API Gateway screenshots |
| 3. AI / ML feature | Amazon Bedrock Claude 3.5 Haiku + Bedrock Knowledge Base / direct InvokeModel fallback | TODO: Bedrock model access + UI result |
| 4. Data persistence | DynamoDB user/document/query state; S3 JSON for flashcards/quizzes | TODO: DynamoDB item + S3 object screenshots |
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
| Object storage | S3 | PDFs, extracted content, flashcards, and quiz JSON are blob/document data. |
| AI model | Claude 3.5 Haiku | Cheapest sufficient model for study Q&A/flashcard/quiz generation during hackathon. |
| RAG | Bedrock Knowledge Base, with local keyword fallback in code | Better grounded answers when KB is ready; fallback keeps demo path alive if KB ingestion has issues. |
| Network | Private Lambda subnet + VPC endpoints, no NAT Gateway | S3/DynamoDB gateway endpoints are free; Bedrock endpoints avoid NAT fixed cost. |
| Observability | CloudWatch dashboard, alarms, logs, custom metrics | Gives operational proof and supports optional Full Observability. |
| IaC | AWS SAM / CloudFormation in `template.yaml` | Reproducible deploy and easier teardown through stack deletion. |

### Trade-offs

1. Lambda vs EC2/ECS: chose Lambda for 48-hour speed and low idle cost. Accepted cold starts and request timeout limits.
2. DynamoDB vs RDS: chose DynamoDB because user state and document metadata are simple access patterns. Accepted weaker ad-hoc querying.
3. Bedrock KB vs direct InvokeModel: chose KB for grounded retrieval. Kept direct/local fallback because KB setup and ingestion can be the riskiest demo dependency.

Required screenshots:
- `docs/evidence/06_architecture_diagram.png`
- `docs/evidence/07_api_gateway_routes.png`
- `docs/evidence/08_lambda_functions.png`
- `docs/evidence/09_cloudformation_stack_outputs.png`

## 4. Cost Discipline

### Cost Screenshots

| Time | Screenshot | Notes |
|---|---|---|
| Day 1 EOD - 2026-05-28 | `docs/evidence/cost_day1_eod.png` | TODO: total, top services |
| Day 2 EOD - 2026-05-29 | `docs/evidence/cost_day2_eod.png` | TODO: total, top services |
| Demo morning - 2026-05-30 | `docs/evidence/cost_demo_morning.png` | TODO: final pre-demo total |

### Top Cost Drivers

| Rank | Service | Cost | Why it appears |
|---|---:|---:|---|
| 1 | TODO: Bedrock / OpenSearch / VPC Endpoint | TODO | TODO |
| 2 | TODO | TODO | TODO |
| 3 | TODO | TODO | TODO |

### Cost Controls

- Budget alert configured through SAM as `studybot-monthly-budget-G15` with SNS notifications at 30%, 50%, and 80%.
- Cost Guard Lambda can freeze backend Lambda reserved concurrency and attach `StudyBotCostDenyPolicy` if budget thresholds are reached.
- Auto-fix Lambda watches CloudTrail events for unauthorized EC2/RDS/OpenSearch creation and can delete costly resources.
- The architecture avoids NAT Gateway and uses S3/DynamoDB gateway endpoints plus Bedrock interface endpoints.

Required screenshots:
- `docs/evidence/10_budget_alert.png` - AWS Budget and SNS subscription confirmed.
- `docs/evidence/11_cost_anomaly_detection.png` - Cost Anomaly Detection enabled.
- `docs/evidence/12_cost_guard_lambda.png` - Cost Guard Lambda and environment variables.
- `docs/evidence/13_cost_explorer_by_service.png` - cost grouped by service.

## 5. Security

### IAM Least Privilege

The Lambda execution role `studybot-lambda-role-G15` is scoped to the app resources:

- S3 read/write/list/delete only for the document bucket and flashcard bucket.
- DynamoDB read/write/query/update/delete only for the StudyBot table.
- Bedrock `InvokeModel`, `Retrieve`, and `RetrieveAndGenerate` for model and knowledge-base use.
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
- `docs/evidence/14_iam_lambda_role_policy.png`
- `docs/evidence/15_vpc_private_subnet.png`
- `docs/evidence/16_vpc_endpoints.png`
- `docs/evidence/17_s3_block_public_access.png`
- `docs/evidence/18_bedrock_model_access.png`

## 6. Monitoring

CloudWatch is used for logs, metrics, dashboarding, and alarms.

Evidence to capture:

| Evidence | What to show |
|---|---|
| `docs/evidence/19_cloudwatch_dashboard.png` | Dashboard `StudyBot-G15` with Lambda invocations/errors/duration and API Gateway requests. |
| `docs/evidence/20_alarm_query_errors.png` | Alarm `StudyBot-G15-QueryErrors` in OK or ALARM state, not INSUFFICIENT_DATA. |
| `docs/evidence/21_alarm_upload_errors.png` | Alarm `StudyBot-G15-UploadErrors` in OK or ALARM state. |
| `docs/evidence/22_log_insights_query.png` | Real Log Insights results from Lambda logs. |
| `docs/evidence/23_custom_metrics.png` | Namespace `StudyBot`, e.g. `FlashcardGenerationLatency`, `FlashcardGenerationSuccess`, `SocraticQueryLatency`. |

Suggested Log Insights query:

```sql
fields @timestamp, @message
| filter @message like /flashcard|query|evaluate|ERROR|WARN/
| sort @timestamp desc
| limit 50
```

## 6.5 Measurement and Decisions

### Decision 1: Use Claude 3.5 Haiku for study generation during the hackathon

**Alternatives considered**

- Claude 3.5 Sonnet: eliminated for default usage because it costs about 3x Haiku per input/output token and the demo workload does not require deep reasoning on long complex documents.
- Local-only stub model: eliminated for final demo because the rules require real Bedrock calls from the app, not console or mock output.
- Larger/fallback models listed in `AI_MODEL_FALLBACKS`: kept only as fallback, not the normal path, to control cost.

**Measurement**

- TODO: Run 5 representative prompts and record average latency: `___ ms`.
- TODO: Record acceptable answer rate on 5 study questions: `___/5`.
- Pricing reference from W7 cost estimate: Haiku `$1.00 / 1M input tokens` and `$5.00 / 1M output tokens`; Sonnet about 3x higher.

**Evidence**

- `docs/evidence/24_bedrock_haiku_answer.png`
- `docs/evidence/25_model_cost_comparison.png`
- CloudWatch custom metric: `SocraticQueryLatency`.

**Trade-off accepted**

- Haiku may produce less polished reasoning than Sonnet on complex material. We accept this because the product goal is fast, affordable study assistance under a 48-hour cost cap; higher models remain fallback only when quality requires it.

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

- `docs/evidence/26_dynamodb_items.png`
- `docs/evidence/27_docs_list_persistence.png`
- `docs/evidence/28_fresh_session_persistence.png`

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

- `docs/evidence/16_vpc_endpoints.png`
- `docs/evidence/29_no_nat_gateway.png`
- `docs/evidence/30_private_route_table.png`

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

- `docs/evidence/31_rag_evaluation_metrics.png`
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
3. Delete the SAM stack:

```bash
sam delete --stack-name studybot-G15 --region ap-southeast-1
```

4. Delete or verify deletion of any separately-created Bedrock Knowledge Base/vector store.
5. Delete CloudFront distribution after disabling it if it was created outside SAM.
6. Delete any OpenSearch Serverless collection if used.
7. Delete any leftover VPC endpoints, security groups, subnets, and VPC if not owned by the stack.
8. Delete Budget/SNS resources if not retained intentionally.
9. Run Cost Explorer after teardown and capture confirmation.

Required teardown screenshots:
- `docs/evidence/32_stack_deleted.png`
- `docs/evidence/33_s3_buckets_empty_or_deleted.png`
- `docs/evidence/34_bedrock_kb_deleted_or_final_state.png`
- `docs/evidence/35_cost_after_teardown.png`

## Screenshot Capture Checklist

Use this checklist while building and demoing. Put all images in `docs/evidence/`.

| File | Screenshot to capture | AWS/UI location |
|---|---|---|
| `01_live_url_loaded.png` | Public HTTPS app loads | Browser |
| `03_upload_flow.png` | Upload success | StudyBot UI |
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
| `26_dynamodb_items.png` | Persisted app state | DynamoDB console |
| `28_fresh_session_persistence.png` | Data still visible in fresh session | Browser |
| `29_no_nat_gateway.png` | NAT Gateway count is zero | VPC NAT Gateway page |
| `31_rag_evaluation_metrics.png` | Precision@K/MRR panel | StudyBot UI |
| `32_stack_deleted.png` | Stack deleted after demo | CloudFormation |
| `35_cost_after_teardown.png` | Final cost after teardown | Cost Explorer |
