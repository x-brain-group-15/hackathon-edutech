# StudyBot — W7 Capstone Starter

**Domain:** EduTech. Upload a lecture (PDF/TXT) → ask questions → get answers grounded in your own notes (RAG).

This starter runs **completely locally** with zero AWS credentials. Switch env vars to flip to AWS Bedrock + KB + S3 + your chosen DB when you're ready to deploy.

---

## Run locally (2 minutes)

```bash
python3 -m venv .venv
source .venv/bin/activate                # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                     # all backends default to LOCAL
uvicorn src.app:app --reload --port 8000

# In another terminal or browser:
curl http://localhost:8000/health
open http://localhost:8000               # macOS — or just navigate to that URL
```

**Smoke test the full flow:**

```bash
# Upload the sample lecture
curl -X POST http://localhost:8000/upload \
  -H "X-User-Id: alice" \
  -F "file=@sample_data/sample_lecture.txt"

# Ask a question
curl -X POST http://localhost:8000/query \
  -H "X-User-Id: alice" -H "Content-Type: application/json" \
  -d '{"question":"What is gradient descent?"}'

# List uploaded docs
curl http://localhost:8000/docs/list -H "X-User-Id: alice"
```

The browser UI at `http://localhost:8000` does the same thing visually.

Run the test suite:
```bash
pytest -v
```

---

## What's in the code

```
src/
├── app.py               FastAPI app + routes. Runs in Lambda, ECS, EC2, App Runner.
├── config.py            Reads ALL settings from env vars. No hardcoded service names.
├── handlers.py          Pure business logic. RAG flow: extract → ingest → retrieve → generate.
└── adapters/
    ├── ai.py            BedrockAI (real Bedrock Converse + KB RAG) | LocalAI (stub)
    ├── storage.py       S3Storage | LocalStorage (filesystem)
    ├── userstore.py     DynamoDBUserStore | PostgresUserStore | SQLiteUserStore
    ├── vector.py        BedrockKBVector | LocalVector (in-memory keyword index)
    └── factory.py       Reads config → instantiates the chosen adapter
```

---

## 9 deployment decisions you still make

When you deploy, every one of these is YOUR call (set in `.env`):

| # | Decision | Env var | Choices |
|---|----------|---------|---------|
| 1 | Compute runtime | (deploy-time) | Lambda (via Mangum) / ECS Fargate / EC2 / App Runner |
| 2 | DB backend | `USERSTORE_BACKEND` | `dynamodb` / `postgres` / `sqlite` |
| 3 | Vector store | `VECTOR_BACKEND` + KB config | Bedrock KB on OpenSearch Serverless / S3 Vectors / Aurora pgvector |
| 4 | Frontend hosting | (deploy-time) | CloudFront+S3 / Amplify / served by backend / ALB+EC2 |
| 5 | Identity | populating `X-User-Id` header | Cognito JWT / hardcoded / signed URL / custom Lambda |
| 6 | VPC topology | (deploy-time) | Subnet layout, SG rules, NAT vs VPC Endpoints |
| 7 | IaC | (deploy-time) | Console / CFN / CDK / Terraform / SAM |
| 8 | Observability | (deploy-time) | CloudWatch dashboard, alarms, custom metrics |
| 9 | Cost optimization | (deploy-time) | Instance sizing, on-demand vs reserved, single-AZ |

Trainers will ask **WHY** for each.

---

## Deploy to AWS — env flip

Once your AWS resources are provisioned, edit `.env`:

```diff
- AI_BACKEND=local
+ AI_BACKEND=bedrock
+ AI_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0

- STORAGE_BACKEND=local
+ STORAGE_BACKEND=s3
+ STORAGE_BUCKET=studybot-uploads-g<N>-<accountid>

- USERSTORE_BACKEND=sqlite
+ USERSTORE_BACKEND=dynamodb           # OR postgres — your call
+ USERSTORE_TABLE=studybot-users

- VECTOR_BACKEND=local
+ VECTOR_BACKEND=bedrock_kb
+ VECTOR_BEDROCK_KB_ID=ABCDEFG123      # from your Bedrock KB
```

Then deploy with your chosen IaC.

**Lambda packaging example:**
```python
# In your Lambda entry file, e.g. lambda_entry.py
from mangum import Mangum
from src.app import app
handler = Mangum(app)
```
Add `mangum>=0.17` to requirements + zip everything + upload.

**ECS Fargate / EC2 / App Runner:**
```
uvicorn src.app:app --host 0.0.0.0 --port 8000
```
Wrap in a Dockerfile of your choice.

---

## Customization ideas (for Criterion I — 10%)

The provided code is the baseline. To earn the Original Architecture criterion you should ADD something on top:

- **Spaced repetition** — track which doc/chunk a user has reviewed and surface stale ones
- **Difficulty levels** — generate quizzes at "easy / medium / hard"
- **Multi-language** — detect input language, prompt accordingly
- **Audio input** — accept .mp3 via S3 + Transcribe → ingest transcript
- **Quiz generation** — new endpoint `/quiz` that produces multiple-choice questions from the user's docs
- **Citation viewer** — frontend highlights the source chunk in the original PDF

Document your customization in `docs/W7_evidence.md` section 7.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'src'` | Run uvicorn from the `studybot/` directory, not from `src/` |
| `[LOCAL_AI_STUB]` in answer | You're still in local mode. Set `AI_BACKEND=bedrock` + AWS creds. |
| `AccessDeniedException` on Bedrock | Enable model access in Bedrock console first (Haiku + Titan Embeddings v2) |
| `botocore.exceptions.NoCredentialsError` | Set AWS creds: `aws configure` or env `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` |
| Bedrock KB returns empty | KB ingestion job hasn't run. Sync the KB in console after uploading docs to its S3 source. |
| SQLite "database is locked" | Don't run multiple uvicorn workers against SQLite. Use DynamoDB or Postgres in production. |
