---
week: 7
title: "W7 Cost Estimates — 3 Reference Projects + Risk Analysis ($100 cap, ap-southeast-1)"
audience: trainer + students
region: ap-southeast-1 (Singapore)
cap: "$100 HARD CAP / group"
last_updated: 2026-05-24
---

# W7 Cost Estimates — ap-southeast-1 (Singapore)

> **Purpose:** Validate that the 3 reference architectures (StudyBot, BudgetBot, DocHub) fit comfortably under the $100 hard cap for the 48-hour hackathon, identify which design choices are dangerous, and give students a realistic burn-rate baseline.

> **Methodology:** All numbers are list price in `ap-southeast-1` (Singapore), 48-hour usage, no free tier, on-demand pricing model. Bedrock foundation-model pricing is uniform across regions; infrastructure (RDS, NAT, VPC endpoints) is ~20-30% higher in Singapore than us-east-1.

> **⚠️ ANTI-BIAS DISCLAIMER:** Reference architectures below show ONE possible service choice per layer. Your team is free to pick ANY service combination — different compute (Lambda/ECS/EC2/App Runner), DB (RDS/DynamoDB/DocumentDB/Aurora), foundation model (Claude/Llama/Titan/Cohere/Mistral), vector store (S3 Vectors/OpenSearch/pgvector/Pinecone), and security area (encryption/audit/secrets/network). Cost numbers are illustrative for those specific choices, not mandates.

---

## Pricing Reference Table — ap-southeast-1 (Singapore)

| Service | Unit | Price (ap-southeast-1) | Notes |
|---------|------|------------------------|-------|
| **Bedrock Claude 3.5 Haiku** | per 1M tokens | $1.00 input / $5.00 output | One of many options — also compare with Llama 3.1 ($0.30/$0.30), Titan ($0.30/$0.40), Cohere ($0.50/$1.50), Mistral. Uniform across regions. |
| **Bedrock Claude 3.5 Sonnet** | per 1M tokens | $3.00 input / $15.00 output | ~3x Haiku — benchmark vs cheaper alternatives before locking in |
| **Bedrock Titan Text Embeddings v2** | per 1M tokens | $0.02 | For KB ingestion |
| **Lambda** | per 1M requests | $0.20 | + $0.0000166667 per GB-second duration |
| **API Gateway HTTP API** | per 1M requests | $1.00 | First 300M/month |
| **API Gateway REST API** | per 1M requests | $3.50 | More expensive than HTTP API |
| **RDS db.t3.micro PostgreSQL Single-AZ** | per hour | $0.026 | Singapore (~44% higher than us-east-1 $0.018) |
| **RDS gp3 storage** | per GB-month | $0.138 | |
| **RDS Proxy** | per hour | $0.018 | Per vCPU equivalent |
| **DynamoDB on-demand write** | per 1M | $1.4135 | |
| **DynamoDB on-demand read** | per 1M | $0.2827 | |
| **S3 Standard storage** | per GB-month | $0.025 | |
| **S3 PUT requests** | per 1K | $0.005 | |
| **S3 GET requests** | per 1K | $0.0004 | |
| **CloudFront (Asia tier)** | per GB | $0.085 | First 10TB; 1TB/month free tier first 12 months |
| **VPC Interface Endpoint** | per hour, per AZ | $0.013 | Singapore (~$0.01 in us-east-1) |
| **VPC Gateway Endpoint (S3, DynamoDB)** | — | FREE | Always prefer when available |
| **NAT Gateway** | per hour | $0.059 | + $0.059/GB data processed. DANGEROUS — avoid if possible. |
| **KMS Customer Managed Key** | per month | $1.00 | + $0.03/10K requests |
| **OpenSearch Serverless** | per OCU-hour | ~$0.288 | Singapore. Min 2 OCU when active. |
| **S3 Vectors** | per GB-month + per query | $0.06 / $0.20 per 1M queries | **Check ap-southeast-1 availability before depending on it.** Launched in us-east-1, us-east-2, us-west-2, eu-central-1 first. |
| **Cognito User Pool MAU** | per MAU/month | FREE up to 50K MAUs | |

---

## Reference A — StudyBot (EduTech)

**Architecture:** CloudFront → S3 static → API Gateway HTTP → Lambda → Bedrock KB (Haiku + Titan v2) + DynamoDB + S3 docs + VPC Interface Endpoint (Bedrock).

### A.1 — With S3 Vectors as KB vector store

| Service | Calculation | Cost |
|---------|-------------|------|
| Lambda | 200 invocations × 512MB × 2s avg = 200 GB-sec + 200 requests | $0.004 |
| API Gateway HTTP | 500 requests | $0.0005 |
| Bedrock Haiku (retrieve+generate) | 500K input tokens + 50K output | $0.50 + $0.25 = **$0.75** |
| Bedrock Titan Embeddings v2 (ingestion) | 1M tokens for documents | $0.02 |
| S3 Vectors | 100MB vector storage + 500 queries | ~$0.01 |
| DynamoDB on-demand | ~500 reads + 200 writes | $0.0004 |
| S3 (documents + static) | 100MB storage + ~500 PUT/500 GET | $0.011 |
| CloudFront | 1GB Asia outbound | $0.085 |
| KMS CMK | 1 key × $1/month × (48h/720h) | $0.07 |
| VPC Interface Endpoint (Bedrock) | $0.013/hr × 48h × 1 AZ | $0.62 |
| **TOTAL (A.1)** | | **~$1.57** |

### A.2 — With OpenSearch Serverless as KB vector store (Singapore)

| Service | Same as A.1 except… | Cost |
|---------|---------------------|------|
| OpenSearch Serverless | 2 OCU × $0.288/hr × 48h | **$27.65** |
| (Drop S3 Vectors $0.01) | | -$0.01 |
| Everything else | (same) | $1.56 |
| **TOTAL (A.2)** | | **~$29.20** |

**Verdict:** A.1 (S3 Vectors) is 2% of the $100 cap — safe. A.2 (OpenSearch Serverless) is ~29% of the cap — comfortable but consumes a large fixed cost on infrastructure alone.

---

## Reference B — BudgetBot (FinTech)

**Architecture:** CloudFront → S3 static → API Gateway REST → Lambda → Bedrock InvokeModel (Haiku, no KB) → RDS PostgreSQL db.t3.micro Single-AZ + RDS Proxy + VPC Interface Endpoint (Bedrock).

| Service | Calculation | Cost |
|---------|-------------|------|
| Lambda | 500 invocations × 512MB × 3s = 750 GB-sec | $0.012 |
| API Gateway REST | 500 requests | $0.0018 |
| Bedrock Haiku InvokeModel | 2000 transactions × 150 input tokens = 300K input + 60K output | $0.30 + $0.30 = **$0.60** |
| RDS db.t3.micro Single-AZ (Singapore) | $0.026/hr × 48h | $1.25 |
| RDS gp3 storage | 20GB × $0.138/GB-month × (48/720) | $0.18 |
| RDS Proxy | $0.018/hr × 48h | $0.86 |
| S3 (statements + static) | 10MB storage + ~200 PUT/GET | $0.002 |
| CloudFront | 500MB Asia outbound | $0.043 |
| KMS CMK | prorated 48h | $0.07 |
| VPC Interface Endpoint (Bedrock) | $0.013/hr × 48h | $0.62 |
| **TOTAL** | | **~$3.65** |

**Verdict:** ~3.7% of the $100 cap. Cheapest of the three. The biggest single cost is RDS (instance + proxy + storage = $2.29), not the AI.

---

## Reference C — DocHub (ProductivityTech)

**Architecture:** CloudFront → S3 static → API Gateway HTTP → Lambda → Bedrock Agent + KB + Action Group Lambda + DynamoDB metadata + S3 docs (multi-tenant prefixes) + Cognito + VPC Interface Endpoints (Bedrock + Secrets Manager).

### C.1 — With S3 Vectors as KB vector store

| Service | Calculation | Cost |
|---------|-------------|------|
| Lambda (main + action group) | 300 invocations × 1024MB × 5s = 1,500 GB-sec | $0.025 |
| API Gateway HTTP | 300 requests | $0.0003 |
| Bedrock Agent + KB (Haiku) | 50 queries × 3K retrieve + 500 generate = 150K input + 25K output | $0.275 |
| Bedrock Titan Embeddings v2 (ingestion of 20 docs) | 2M tokens | $0.04 |
| S3 Vectors | 200MB + 50 queries | ~$0.01 |
| DynamoDB on-demand | ~300 reads + 100 writes | $0.0003 |
| S3 (docs + static) | 200MB + ~400 PUT/GET | $0.012 |
| CloudFront | 1GB Asia outbound | $0.085 |
| KMS CMK | prorated 48h | $0.07 |
| Cognito | <100 MAU | FREE |
| VPC Interface Endpoints × 2 (Bedrock + Secrets Manager) | 2 × $0.013/hr × 48h | $1.25 |
| **TOTAL (C.1)** | | **~$1.77** |

### C.2 — With OpenSearch Serverless (Singapore)

| Service | Same as C.1 except… | Cost |
|---------|---------------------|------|
| OpenSearch Serverless | 2 OCU × $0.288 × 48 | $27.65 |
| (Drop S3 Vectors $0.01) | | -$0.01 |
| Everything else | (same) | $1.76 |
| **TOTAL (C.2)** | | **~$29.40** |

**Verdict:** C.1 (S3 Vectors) is 1.8% of the $100 cap. C.2 (OpenSearch Serverless) is ~29% — same pattern as Reference A.

---

## "Phạm gì không?" — Risk Analysis vs $100 Cap

### Best-case spend (all 3 references, S3 Vectors path)

| Project | Spend | % of $100 cap | Headroom |
|---------|-------|---------------|----------|
| StudyBot (A.1) | $1.57 | 1.6% | $98.43 |
| BudgetBot (B) | $3.65 | 3.7% | $96.35 |
| DocHub (C.1) | $1.77 | 1.8% | $98.23 |

### Realistic spend (OpenSearch Serverless for KB groups)

| Project | Spend | % of $100 cap | Headroom |
|---------|-------|---------------|----------|
| StudyBot (A.2) | $29.20 | 29.2% | $70.80 |
| BudgetBot (B) | $3.65 | 3.7% | $96.35 |
| DocHub (C.2) | $29.40 | 29.4% | $70.60 |

**All 3 reference projects fit comfortably under $100 cap.** No architecture as designed exceeds the cap.

### Bonus-tier eligibility check (under $30 + clean teardown)

| Project | Eligible for bonus path H (<$30)? |
|---------|-----------------------------------|
| StudyBot S3 Vectors | ✅ Yes ($1.57) |
| StudyBot OpenSearch Serverless | ⚠️ Borderline ($29.20) — any extra drift kicks it out |
| BudgetBot | ✅ Yes ($3.65) |
| DocHub S3 Vectors | ✅ Yes ($1.77) |
| DocHub OpenSearch Serverless | ⚠️ Borderline ($29.40) — any extra drift kicks it out |

---

## Worst-case scenarios — what blows the $100 cap?

### Killer #1: NAT Gateway running 24/7

- $0.059/hour × 48h = **$2.83** + data processing ($0.059/GB)
- 100GB processed during 48h debug = $5.90 → total $8.73 just for NAT
- Combined with OpenSearch Serverless ($29.65) + NAT ($8.73) = $38.38 base cost before any AI

**Fix:** Use VPC Endpoints (Gateway for S3/DynamoDB = free; Interface for Bedrock = $0.62 per AZ for 48h). One Interface Endpoint costs 22% of one NAT Gateway and is enough.

### Killer #2: RDS Multi-AZ

- Single-AZ db.t3.micro Singapore = $0.026/hr → 48h = $1.25
- Multi-AZ db.t3.micro Singapore = $0.052/hr → 48h = **$2.50** (doubled)
- Not catastrophic but wasted on a 48-hour hackathon — failover protection has no demo value

**Fix:** Single-AZ is fine for hackathon. Document the trade-off in Evidence Pack.

### Killer #3: Claude 3.5 Sonnet in dev loop

- Haiku: $1.00 input / $5.00 output per 1M tokens
- Sonnet: $3.00 input / $15.00 output per 1M tokens
- Sonnet is **3x input / 3x output** = effectively 3x cost per call

Real example: a team debugging RAG with 50 iterations × 5K input + 1K output tokens each:
- Haiku: 250K × $1 + 50K × $5 = $0.25 + $0.25 = **$0.50**
- Sonnet: 250K × $3 + 50K × $15 = $0.75 + $0.75 = **$1.50**

Single debug session = +$1.00 difference. Across a 2-day hackathon with 10+ debug sessions = +$10-15 wasted.

**Fix:** Cheapest sufficient model for ALL dev (compare across Claude/Llama/Titan/Cohere/Mistral). Upgrade for demo only if measurement justifies.

### Killer #4: OpenSearch Serverless over-provisioned

- Default minimum is 2 OCU (1 indexing + 1 search) = $27.65 for 48h
- If a team accidentally allocates 4 OCU = $55.30 — over half the budget gone before AI calls
- If left running an extra day past Friday before teardown = +$13.82

**Fix:** Use S3 Vectors if available in ap-southeast-1. If not, leave OpenSearch Serverless at default minimum and delete the collection immediately after Friday demo (do not wait until Sunday).

### Killer #5: Forgetting teardown

- An idle RDS db.t3.micro Singapore left running 1 month past Friday = $0.026 × 720h = **$18.72**/month
- An idle OpenSearch Serverless collection = $0.288 × 2 × 720h = **$414.72**/month
- An idle NAT Gateway = $0.059 × 720h = **$42.48**/month

**Fix:** Teardown mandate by Sun 1/6 EOD. Cost Explorer screenshot Mon 2/6 confirms. Bonus path H requires this.

### Combined worst-case (no fixes applied)

| Bad choice | Cost (48h) |
|------------|------------|
| OpenSearch Serverless 2 OCU | $27.65 |
| NAT Gateway 24/7 | $2.83 |
| Multi-AZ RDS db.t3.micro | $2.50 |
| Sonnet in dev (10 sessions) | $15.00 |
| 1 extra OCU pair on OpenSearch | $13.82 |
| Forgetting to delete 1 Lambda layer w/ orphan resources | varies |
| **Approximate ceiling** | **~$62** |

Even the "everything wrong" scenario for these 3 reference architectures fits under $100. **The hard cap is a comfortable safety net at $100, not a knife-edge.**

---

## Recommendations for students

1. **Default to S3 Vectors** for KB use cases if available in ap-southeast-1. Confirm in AWS Console → Bedrock → Knowledge Bases → Create → Vector store options before locking architecture.
2. **One Interface Endpoint per service**, not per AZ. You only need one AZ for a hackathon.
3. **No NAT Gateway** unless you have a hard requirement to call non-AWS services. Check first whether you can use a VPC endpoint.
4. **Cheapest sufficient foundation model for dev.** Benchmark Claude/Llama/Titan/Cohere/Mistral on YOUR task before picking. Reserve expensive models for demo recording at most.
5. **Single-AZ RDS** is fine. Multi-AZ is for production with real SLAs.
6. **Tag every resource on creation** with `Project=W7Capstone`, `Team=G<N>`, `Owner=<name>`. Filter Cost Explorer by `Team=G<N>` tag to see your group's spend isolated.
7. **Set Budget alert at $80** (80% of $100 cap) with confirmed SNS email subscription before deploying anything paid.
8. **Take 3 Cost Explorer screenshots:** Day 1 EOD, Day 2 EOD, Friday pre-demo. Required for Evidence Pack section 4.
9. **Teardown by Sunday 1/6 EOD.** An idle OpenSearch Serverless collection costs $414/month — that's your money, not ours.
10. **Bonus path H:** total spend under $30 + clean teardown = +0.25. Easy to hit with S3 Vectors, harder with OpenSearch Serverless.

---

## Recommendations for trainers

1. During Wed/Thu spot-checks, ask: "Show me your Bedrock KB vector store choice." If they picked OpenSearch Serverless and S3 Vectors is available, suggest the switch.
2. At Wed 11:00 sign-off, verify Budget alert is at $80 (not the old $40 / $50 cap value) and the SNS subscription is confirmed.
3. If a group hits $40 by Thursday morning, they are not in danger of the $100 cap — but it is unusual and worth asking what they deployed. NAT Gateway, Multi-AZ, or 4-OCU OpenSearch Serverless are the most likely culprits.
4. Emergency intervention threshold: **$70 by Thursday morning** is the new "stop building, delete unnecessary resources" line. (Previously $30 under $50 cap; scaled proportionally to $70 under $100 cap.)
5. The reference architectures as designed all fit under $30, leaving plenty of room for groups to add features. Use this as the baseline — if a group is at $50+ for the same architecture, something is wrong.

---

## Comparison vs. previous $50 cap

| Tier | Old (cap $50) | New (cap $100) |
|------|---------------|----------------|
| Bonus eligibility | <$15 + clean teardown | **<$30** + clean teardown |
| Strong discipline | $15-30 | **$30-60** |
| OK within cap | $30-50 | **$60-100** |
| Hard cap exceeded → Criterion IV capped at 3 | $50+ | **$100+** |
| Budget alert threshold (80%) | $40 | **$80** |
| Emergency intervention (trainer spot-check) | $30 by Thu | **$70 by Thu** |

---

## Sources

- AWS Bedrock pricing: https://aws.amazon.com/bedrock/pricing/
- AWS Lambda pricing ap-southeast-1: https://aws.amazon.com/lambda/pricing/
- AWS RDS PostgreSQL pricing: https://aws.amazon.com/rds/postgresql/pricing/
- AWS DynamoDB pricing: https://aws.amazon.com/dynamodb/pricing/on-demand/
- AWS S3 pricing: https://aws.amazon.com/s3/pricing/
- AWS CloudFront pricing: https://aws.amazon.com/cloudfront/pricing/
- AWS OpenSearch Serverless pricing: https://aws.amazon.com/opensearch-service/pricing/
- AWS S3 Vectors: https://aws.amazon.com/s3/features/vectors/
- AWS VPC pricing (Endpoints, NAT Gateway): https://aws.amazon.com/privatelink/pricing/

All numbers are list price, ap-southeast-1 (Singapore), no Free Tier credits, on-demand. Validated against AWS public pricing pages as of 2026-01.