# Week 7 — Capstone Hackathon: Ship Production-Ready AI in 48 Hours

## The One Paragraph You Need to Read Right Now

W7 is a 48-hour hackathon. No new courses. No new labs. Two days to build a real AI SaaS app on your personal AWS account, get it live at a public URL, and demo it to a judging panel on Friday. You have already learned everything you need across W1-W6. This week you ship it. The cost ceiling is $100 HARD CAP per group — this is real money from your real account. Cost discipline is graded, and going over $100 total caps your deployment score. A working public URL is 40% of your score. A brilliant architecture diagram with a broken demo gets a cap. Ship first. Polish second.

---

## What You're Building

Your group picks one domain and builds an AI-powered SaaS platform on it:

| Domain | App Concept | Core AI Flow |
|--------|------------|--------------|
| EduTech | "AI Study Buddy" | Upload lecture PDFs/slides → AI summarizes, generates flashcards, answers questions about the content |
| FinTech | "AI Money Coach" | Upload bank statements (PDF/CSV) → AI categorizes transactions, gives spending insights, answers budget questions |
| ProductivityTech | "AI Document Hub" | Upload contracts/reports/docs → AI searches across all documents, answers questions, summarizes key sections |

The technical stack is the same regardless of domain. Only the user-facing features differ.

---

## Schedule at a Glance

| Day | What Happens |
|-----|-------------|
| Mon 25/5 + Tue 26/5 | Optional prep: account setup, Bedrock access, domain choice, architecture draft |
| Wed 28/5 | DAY 1 BUILD — Architecture lock + infra deploy + happy path working |
| Thu 29/5 | DAY 2 BUILD — AI integration + monitoring + Evidence Pack + demo prep |
| Fri–Sat 30–31/5 | DEMO DAY (2 days, presentation-focused) — 40-min slot per group: Architecture Walkthrough 14p + Individual QnA 12p |
| Sun 1/6 EOD | Teardown deadline — delete every resource, take screenshot |
| Mon 2/6 | Commit teardown screenshot to repo — final deliverable |

---

## Mon 25/5 + Tue 26/5 — Prep Days (Optional but Important)

Do not build production infrastructure during prep days. That wastes money before the clock starts. Use these days to eliminate blockers that will otherwise eat into your 48 build hours.

**What to do during prep days:**

**Pre-flight safety setup (required before Wednesday architecture sign-off):**

Your trainer will check all five of these before approving your architecture. Missing any one = no sign-off until fixed.

- [ ] Enable MFA on your AWS root account (evaluated at QnA and required for sign-off)
- [ ] Set up a Budget alert at $80: AWS Budgets → Create budget → Cost budget → $80 threshold → SNS email. Confirm the subscription email — this means you receive and click the confirmation link in the email. A budget configured but not confirmed does not protect you.
- [ ] Enable Cost Anomaly Detection: Cost Management → Cost Anomaly Detection → Create monitor. Free, ML-based, catches runaway spend before Cost Explorer shows it.
- [ ] Agree on tagging strategy for every resource: `Project=W7Capstone`, `Team=G<N>`, `Owner=<name>`, `Environment=hackathon`.
- [ ] Bedrock model access enabled (see below).

**Bedrock access (required before Wednesday):**
- AWS Console → Amazon Bedrock → Model access → Request access for:
  - Anthropic Claude Haiku (use in dev — fast and cheap)
  - Anthropic Claude Sonnet (use only for final demo if you need it)
  - Amazon Titan Embeddings v2 (required for Knowledge Base)
- Wait 5-10 minutes after approving before testing. If you get `AccessDeniedException` immediately after approving, wait and try again.

**Architecture draft:**
- Pick your domain as a group and commit to it
- Draft your architecture on paper or draw.io — all 7 mandatory capabilities must be present before you get architecture sign-off. For each mandatory capability, your team picks the service that fits your use case and must be ready to say WHY. Then pick one optional capability to attempt on Day 2.

**7 Mandatory Capabilities (required — every group must demonstrate all of these on Friday):**

| # | Capability | Must deliver | Example services (your choice) |
|---|-----------|-------------|-------------------------------|
| 1 | User-Facing Entry | Public HTTPS entry — static frontend hosting AND/OR API endpoint. EDGE/ENTRY layer, NOT compute. | Static: S3+CloudFront, Amplify · API entry: API Gateway, ALB, Lambda Function URL, AppSync, App Runner endpoint |
| 2 | Application Compute | Where backend code RUNS — process request, AI call, business logic. SEPARATE from #1. | Lambda, EC2, ECS/Fargate, App Runner, Step Functions, AppSync resolver |

**Common pairings — each side counts as separate mandatory slot:** ALB+EC2 → ALB is #1, EC2 is #2 · API Gateway+Lambda → API GW is #1, Lambda is #2 · Lambda Function URL → same Lambda fills BOTH #1 and #2 (articulate which role)
| 3 | AI / ML Feature | At least 1 intelligent feature working end-to-end | Bedrock (KB+Agent OR InvokeModel), Comprehend, Rekognition, etc. |
| 4 | Data Persistence | User state across sessions | RDS, Aurora, DynamoDB, ElastiCache, etc. |
| 5 | Object Storage | Files/blobs | S3 (any class) |
| 6 | Network Foundation | DB not public-facing — proper isolation | VPC + subnets + Security Groups |
| 7 | Identity & Access (baseline) | IAM least-privilege roles for all services. User-facing auth is your choice: IAM-only, Cognito, or signed URLs | IAM roles (required), Cognito, signed URLs, custom JWT |

**3 Optional Capabilities (pick ONE — not all three):**

| # | Capability | What earns bonus credit |
|---|-----------|------------------------|
| 8 | Full Observability | CloudWatch dashboard + at least 1 custom metric (PutMetricData) + at least 1 alarm in OK/ALARM state (not INSUFFICIENT_DATA) + at least 1 saved Log Insights query |
| 9 | Advanced Cost Insights | 3 daily Cost Explorer screenshots + written breakdown observation + cost-per-feature analysis + Cost Anomaly Detection alert demo |
| 10 | Advanced Security | **Pick ONE area + go deep — no specific service forced.** Encryption (KMS CMK+rotation / KMS managed / app-layer) · Audit (CloudTrail+Config / Security Hub / GuardDuty / Inspector) · Secrets (Secrets Manager rotation / Parameter Store / Vault) · Network (WAF / Shield / SG strictness / VPC Flow Logs). Demonstrate WITH measurement. |

Pick ONE optional and do it well. 1 done well drives your scores higher than 3 half-done. Time budget: 12-14 hours for 7 mandatory, 2-3 hours for one optional.

For each mandatory capability row in your architecture diagram, be ready to answer: "Why this service for this capability, not an alternative?"
- Assign roles: who is deploying what on Wednesday morning

**Tagging strategy — agree this now:**
Every resource you deploy must have these 4 tags:
- `Project=W7Capstone`
- `Team=G<your-group-number>`
- `Owner=<member-name-who-deployed-it>`
- `Environment=hackathon`

---

> 📝 **Day 1 / Day 2 below is a SUGGESTED checkpoint rhythm — not a mandate.**
>
> If your team has its own 48-hour plan, follow that. Split the work however you want (sprint at night, shifts, different parallelization, AI integration first then infra, etc.). **Only hard deadline = Friday 09:00 with a working URL + presentation ready.** The day-by-day breakdown is a default for teams without a plan + a guide for trainer spot-checks.

## Wednesday 28/5 — Day 1 Build (suggested rhythm)

### Morning (9:00-12:00) — Architecture Lock

**9:00-9:30**: Trainer kick-off. Listen — cost rules, tagging rules, architecture sign-off process are all covered here.

**9:30-11:00**: Finalize your architecture diagram. Every layer must be in the diagram before you get sign-off. No sign-off = no infra deploy in the afternoon.

**11:00-12:00**: Architecture review with trainer or mentor. Come prepared with:
- Printed or shared diagram with all 7 mandatory capabilities mapped to your chosen services
- For each mandatory capability: a one-line "why we chose this service for this capability" (not just the service name)
- Your pre-flight safety checklist: Budget alert confirmed + Cost Anomaly Detection enabled + Bedrock model access granted + MFA on root + tagging strategy agreed
- Which optional capability (#8 Full Observability, #9 Advanced Cost Insights, or #10 Advanced Security) your group plans to attempt on Day 2 — or "none" if you are not attempting one
- Your role assignments (who builds what mandatory capability on Wednesday)

Do not leave this review without your trainer's verbal go-ahead. It protects you from building the wrong thing — and the trainer will push back on any service choice you cannot justify.

### Afternoon (13:00-18:00) — Infra Deploy + Happy Path

Deploy in parallel — split the work across team members. Each person owns one or more mandatory capabilities from your architecture sign-off. Deploy the services YOUR TEAM chose for each mandatory capability. No optional capabilities today — that is Day 2.

| Mandatory Capability | Deploy the service(s) your team chose during architecture sign-off |
|---------------------|-------------------------------------------------------------------|
| Network Foundation (Mandatory #6) | Your chosen network isolation (e.g., VPC + subnets + SGs, DB in private subnet) |
| Identity & Access baseline (Mandatory #7) | IAM execution roles for all compute services. If using Cognito: User Pool + app client. |
| Object Storage (Mandatory #5) | S3 bucket (block public access, versioning on) |
| Data Persistence (Mandatory #4) | Your chosen database (per architecture sign-off) in private subnet |
| Application Compute (Mandatory #2) | Your chosen compute + API layer (e.g., Lambda + API Gateway HTTP API) |
| User Interface (Mandatory #1) | Your chosen frontend approach (e.g., S3 static hosting + CloudFront) |

Suggested deploy order (dependencies matter): Network → IAM → Storage → DB → Compute → API → Auth → Frontend

**By 17:00 — wire your happy path:**
1. Hit your frontend URL in a browser → login page appears
2. Log in via Cognito → get JWT → make authenticated request to API
3. API → Lambda → write one test record to DB → read it back
4. Lambda → Bedrock InvokeModel with a simple prompt → get a response

This is a plumbing test, not a finished product. If plumbing works, Thursday's AI integration will go smoothly.

**Day 1 EOD checklist — all 7 mandatory capabilities status:**
- [ ] Mandatory #1: Public URL (HTTPS) accessible (CloudFront or ALB serving your frontend)
- [ ] Mandatory #2: API endpoint returning a response via Lambda + API Gateway (any response)
- [ ] Mandatory #3: Bedrock returned something in Lambda CloudWatch logs (full AI integration is Day 2)
- [ ] Mandatory #4: DB write + read working (at least one test record in your chosen database)
- [ ] Mandatory #5: S3 bucket created with Block Public Access enabled
- [ ] Mandatory #6: DB in private subnet, SG scoped to compute SG — confirmed in console
- [ ] Mandatory #7: Lambda IAM execution role has named actions (no AdministratorAccess or `*` wildcards)
- [ ] Pre-flight: Cost <$5 (check Budget alert — Cost Explorer lags 12-24 hours)
- [ ] Pre-flight: Budget alert email subscription confirmed

If you're blocked on any of these — message your mentor or trainer via Slack that evening. Do not wait until Thursday morning.

---

## Thursday 29/5 — Day 2 Build (suggested rhythm)

### Morning (9:00-12:00) — AI Integration

Wire the full AI feature. Two paths:

**Path A — Knowledge Base + Agent (Recommended if your domain involves documents):**
1. Create an S3 bucket as your KB data source (use your existing KMS-encrypted bucket)
2. Create a Bedrock Knowledge Base: S3 data source → Titan Embeddings v2 → OpenSearch Serverless vector store
3. Run one ingestion job (one sync — don't re-run repeatedly, it costs money)
4. Create a Bedrock Agent, connect the KB, optionally add a Lambda action group
5. Update your main Lambda to call `bedrock-agent-runtime:InvokeAgent` instead of InvokeModel
6. Test: upload a document → ask a question about it → get a relevant answer

**Path B — Direct InvokeModel (Faster, use if you're behind):**
1. Your Lambda calls `bedrock:InvokeModel` with Claude Haiku
2. Build the prompt server-side: pull relevant context from your DB + prepend to user message
3. Return the response through your API to the frontend
4. Document in your Evidence Pack why you chose this path (this is a legitimate architectural decision)

OpenSearch Serverless for Path A takes 10-20 minutes to provision — start KB creation first thing in the morning, then work on other things while it provisions.

### Afternoon (13:00-17:00) — Optional Capability + Evidence Pack + Demo Prep

**13:00-14:30 — Optional capability (the one your group declared at Wednesday sign-off):**

Pick ONE and do it well. Time budget is roughly 2-3 hours. Do not attempt all three.

**If your group chose Full Observability (#8):**
- Create a CloudWatch dashboard with at least 3 widgets: Lambda invocations/errors, API Gateway 4xx/5xx, and one custom metric of your choice (use `put_metric_data` from your Lambda code)
- Create at least 1 alarm on your custom metric or Lambda error rate — it must be in OK or ALARM state, not INSUFFICIENT_DATA. Run your demo path once to generate data points before setting the alarm.
- Save a Log Insights query: filter your Lambda logs for errors in the last hour

**If your group chose Advanced Cost Insights (#9):**
- Take your Day 2 EOD cost screenshot NOW at 14:00 — not at 17:30 when you are rushing
- Write a one-paragraph breakdown observation: which service is your top cost driver, was that expected, what could you change to reduce it?
- Calculate cost-per-feature: e.g., "each Bedrock Haiku call costs approximately $0.0001 in tokens, so 2000 categorizations = $0.20 in Bedrock tokens"
- Show Cost Anomaly Detection alert is enabled and configured in console — screenshot for Evidence Pack

**If your group chose Advanced Security (#10):**
- Create a KMS Customer Managed Key (not default aws/s3 key) and apply it to your S3 bucket and/or database encryption
- Enable automatic key rotation (KMS console → your key → enable automatic rotation — one click)
- Optional additional: deploy an AWS Config rule to check S3 Block Public Access is enabled on all buckets in the account
- Screenshot the CMK in console showing key rotation enabled + the resource encrypted with it

**If your group declared no optional capability:**
- Spend this time on Evidence Pack (sections 1-6 complete) and demo prep
- You are aiming for Criterion IV = 4, which is a strong outcome

**14:30-16:00 — Cost screenshot + Evidence Pack:**
- Take your Day 2 EOD cost screenshot NOW (Cost Explorer → last 24h → group by service). Do this at 14:30, not at 17:30 when you're rushing.
- Draft your Evidence Pack (`docs/W7_evidence.md`) — aim for sections 1-6.5 complete by EOD:
  1. Cover (group ID, member names, live URL, GitHub repo)
  2. Domain + use case + target users + market reasoning + **named real-world parallel** (Quizlet AI / Cake AI / Harvey AI etc. — see project announcement for full list)
  3. Architecture diagram + service decision table + 3 trade-off justifications
  4. Cost section: Day 1 EOD screenshot + Day 2 EOD screenshot + top-3 cost drivers
  5. Security section: IAM role list, KMS key ARN, MFA confirmed
  6. Monitoring section: dashboard screenshot, alarm config, Log Insights query
  6.5 **Measurement & Decisions** ★ NEW — required, anti-đối phó. At least 2 structured DECISION blocks:

```
DECISION: [Specific choice — e.g., "Bedrock Haiku for transaction classification, few-shot prompt with 8 examples"]

ALTERNATIVES CONSIDERED:
- [Option A] — eliminated because: [reason with a number]
- [Option B] — eliminated because: [reason with a number]

MEASUREMENT:
- [Metric 1] = [number with unit] — [how measured]
- [Metric 2] = [number with unit] — [how measured]

EVIDENCE:
- [Screenshot path / Cost Explorer link / spreadsheet / log query]

TRADE-OFF ACCEPTED:
- [What you gave up — be specific]
```

**Scoring:** Vague "we chose Bedrock, it works" = 0 for that block. Concrete numbers + screenshot + named trade-off = full credit. 2 strong blocks beat 6 weak ones.

**Pick decisions that mattered:** compute (Lambda vs ECS), DB (DynamoDB vs Postgres vs DocumentDB), AI model (Haiku vs Sonnet vs few-shot vs zero-shot), chunking strategy, retrieval threshold. NOT "Python vs Node" (incidental).

**Link to cost bonus:** to qualify for the under-$30 cost bonus (Path H), §6.5 must document what you cut to stay lean. Cheap deployment without measured trade-offs = under-deployment, not discipline. Bonus denied.

**16:00-17:00 — Demo prep:**
- Write your 3-minute demo script word-by-word. Practice it once.
- Record your demo video (3 min max) — this is your insurance if the live demo fails on Friday. Use Loom, OBS, or QuickTime. Upload to repo as `docs/demo.mp4` or post as YouTube unlisted and link in README.
- Build your slides (12-18 pages) and upload as `docs/slides.pdf` — Architecture section gets ~10 slides since it's the 14-min focus of the presentation
- Final test: open your live URL from a different network (use your phone's hotspot — this simulates what the trainer will see)

**Day 2 EOD checklist:**

Mandatory (all required):
- [ ] Mandatory #3 (AI): AI feature working end-to-end — KB responds or InvokeModel responds and result visible in UI
- [ ] All 7 mandatory capabilities demonstrable from a phone hotspot (different network from your laptop)
- [ ] Evidence Pack sections 1-6 in `docs/W7_evidence.md`
- [ ] Demo video committed to repo (or YouTube link in README) — do not skip this
- [ ] Slides at `docs/slides.pdf`
- [ ] Day 2 EOD cost screenshot in Evidence Pack section 4
- [ ] Total spend <$60 (warning zone $60-100; $100+ = HARD CAP exceeded — Criterion IV capped at 3)

Optional capability status (note for your Evidence Pack):
- [ ] Full Observability: CloudWatch alarm in OK or ALARM state (not INSUFFICIENT_DATA) + custom metric publishing + Log Insights query saved
- [ ] Advanced Cost Insights: 3 screenshots taken + breakdown paragraph written + cost-per-feature calculated
- [ ] Advanced Security: your chosen area implemented (encryption / audit / secrets / network) + Evidence Pack §6.5 has measurement (what's encrypted, rotation date, alarm count, etc.)
- [ ] No optional attempted: OK — aim for complete Evidence Pack and strong demo prep

---

## Fri–Sat 30–31/5 — Demo Day

### What the Day Looks Like

Groups present in 45-minute slots (40 min present + 5 min buffer). Groups 1–8 present Friday, Groups 9–15 present Saturday morning.

**Your 40-minute slot has five parts — Architecture Walkthrough is the biggest:**

| Part | Time | What Happens |
|------|------|-------------|
| Pitch + Vision | 5 min | Domain story — who's the user, why this use case matters. Set the stage. |
| Live Demo | 7 min | Trainer opens your URL. You narrate: log in, upload, AI processes, persistence check (write Thu, read Fri). |
| Architecture Walkthrough ★ | 14 min | THE BIG ONE. Walk diagram + every service you chose + 1 optional capability + 9 decisions + 2-3 real trade-offs. This is where you prove you thought about it. Rehearse this. |
| Individual QnA | 12 min | Trainer picks 2-3 people at random. Each answers a deep question — probes get harder after they hear your walkthrough. |
| Cost + Lessons Learned | 2 min | Show actual Cost Explorer numbers. Say what you'd do differently. |

### What Friday Morning Looks Like for You

- Arrive before 8:45
- Open your live URL at 8:45 and run a warm-up query (primes your AI backend for fast response)
- Have your slides open and ready to share screen
- Have your demo script memorized (not reading from notes)
- Have your Evidence Pack `docs/W7_evidence.md` open in a browser tab
- Have your demo video queued in case the live demo fails

### Individual QnA — Be Ready

Individual QnA is 30% of your final score. Any team member can be called on. You don't know who will be picked. You cannot pass your question to someone else. Every person in your group must understand:
- Why you chose DynamoDB vs RDS (or vice versa)
- What your Lambda IAM execution role allows and why
- How your AI feature actually works (end-to-end flow)
- What your top-3 cost drivers are and why
- How to debug a broken Lambda (where do you look first)
- What teardown order you're following and why VPC comes last

Prepare the whole team, not just the person who built each piece.

---

## What You Must Show on Friday

Friday Part 1 is trainer-verified: all 7 mandatory capabilities. Friday Part 2 is your optional capability (if attempted). Then QnA.

**7 mandatory capabilities — trainer verifies each one:**

1. **Public URL (HTTPS)** — trainer opens it in their browser, app loads, no SSL errors (#1 User Interface)
2. **Backend processes a request** — API Gateway → Lambda → response returned to the UI (#2 Application Compute)
3. **AI responds** — real Bedrock invocation, result visible in the UI, not a hardcoded string (#3 AI/ML Feature)
4. **State persists** — data written on Thursday is readable in a fresh Friday session (#4 Data Persistence)
5. **S3 bucket** — document or asset storage in S3, Block Public Access confirmed (#5 Object Storage)
6. **Network isolation** — DB in private subnet, SG scoped to compute SG, not `0.0.0.0/0` inbound (#6 Network Foundation)
7. **IAM least-privilege** — Lambda execution role has named actions, not wildcards (#7 Identity and Access)

**Optional capability (if attempted):** After mandatory verification, tell the trainer which optional capability you attempted. Show what you built. Partial progress earns partial credit.

**Cost evidence** — Cost Explorer filtered by `Team=G<N>` tag, 3 daily screenshots in Evidence Pack, total under $100.

**Evidence Pack** — `docs/W7_evidence.md` with all 8 sections. Must be committed to repo before your slot.

If your live demo breaks on Friday: your demo video is your backup. If you have no demo video either: the trainer's ability to score Criterion IV (40%) is severely limited. Record the video Thursday afternoon. No exceptions.

---

## Quality Bar — Ship, Don't Polish

This is a hackathon, not a startup launch. Your code is allowed to look ugly. What matters is that the demo works.

### What is graded (put your time here)

| Graded | |
|--------|--|
| Architecture decisions: can you explain why you chose each service? | |
| 7 mandatory capabilities working on Friday | |
| Live URL that the trainer can open and interact with | |
| AI feature producing a real, observable result | |
| Persistent state: data written on Thursday readable on Friday | |
| Evidence Pack with all 8 sections | |
| Cost discipline: Budget alert + tagging + under $100 | |

### What is NOT graded (do not spend build time here)

| NOT graded | |
|------------|--|
| Code quality or structure — a single-file Lambda is fine | |
| Frontend looks and styling — a basic HTML form is enough | |
| Comprehensive error handling — let errors throw and log to CloudWatch | |
| Unit tests or integration tests | |
| Edge cases — the happy path is the bar | |
| Performance — fast enough for a demo is fast enough | |
| Full auth flow — a hardcoded test user is fine for the demo | |
| Mobile responsive design | |
| Slide design — readable is enough | |

### How to spend your time

Spend Wednesday getting all 7 mandatory capabilities deployed and connected. Spend Thursday morning completing your AI integration and getting the full happy path end-to-end. Spend Thursday afternoon on ONE optional capability (your choice — pick the one your group is closest to finishing) and writing your Evidence Pack. Do not try to polish everything.

### Permission to skip

You do not need a beautiful UI. You do not need a comprehensive auth flow. You do not need unit tests. You do not need pretty slides. You do not need to handle every edge case. Ship the demo.

The three most common over-engineering mistakes to avoid:

- **Spending 4 hours on a React frontend** when a plain HTML form satisfies capability #1 in 30 minutes. If your backend is not deployed yet and you are still styling your frontend, stop and deploy the backend.
- **Setting up full Cognito signup, email verification, and password reset** when a hardcoded test user or IAM-based access satisfies capability #7 and costs zero hours. Cognito is optional.
- **Refactoring code mid-hackathon.** "We should split this Lambda into three clean modules" is not a thought that belongs in your head between Wednesday morning and Friday 09:00. Ship the working messy Lambda. Note in your Evidence Pack that you'd refactor in Phase 2.

---

## Domain Picker Guide

Not sure which domain fits your team? Use this:

**EduTech — "AI Study Buddy"**
Pick this if your team has at least one person who has worked with PDFs programmatically, or who enjoys content/education products. The core challenge is document ingestion (Bedrock KB) and making AI answers relevant to the uploaded material. The user value is immediately obvious — it is easy to demo.

**FinTech — "AI Money Coach"**
Pick this if your team is comfortable with CSV parsing and structured data. The core challenge is transforming uploaded bank statement CSVs into a format the AI can reason about, then persisting the categorized data in your DB. The demo is compelling because real financial data + AI insights is a hot market.

**ProductivityTech — "AI Document Hub"**
Pick this if your team wants to build a multi-tenant document search system — the broadest scope. The core challenge is multi-user document isolation (each user only sees their own docs) and fast search across a large KB. Slightly harder to demo but the most scalable product concept.

All three domains use the same AWS tech stack. Choose based on what your team finds motivating.

---

## Cost Survival Tips

Cost discipline is graded. Here is how to stay under $100 without sacrificing your demo. $100 is the HARD CAP — going over it caps your deployment score.

**Use free tier wherever possible:**
- Lambda: first 1M requests per month free
- DynamoDB: 25 GB + 25 WCU + 25 RCU free permanently
- API Gateway: 1M calls/month free for first 12 months
- S3: 5 GB storage + 20K GET + 2K PUT free for 12 months
- Cognito: 50K MAU free

**For the things that cost money:**
- Bedrock: pick the cheapest sufficient model BEFORE locking in. Compare $/1M tokens across Claude family, Llama, Titan, Cohere, Mistral. Run 5-10 representative queries on 2 candidates → measure accuracy/quality → pick. Upgrade for demo recording only if measurement justifies the cost differential. Document in Evidence Pack §6.5.
- RDS: use db.t3.micro single-AZ. Do not use Multi-AZ. Stop the RDS instance at end of Day 1 if you're not testing it overnight (but remember to start it again Thursday morning).
- NAT Gateway: if you don't genuinely need internet access from private subnets, skip NAT Gateway entirely. Use VPC endpoints for S3, DynamoDB, and Bedrock — they're free or low cost. NAT Gateway costs ~$1.50/day — that's $3 for two nights if left running.
- KMS: $1/key/month (negligible — use CMK for S3 and chosen DB encryption as required)
- OpenSearch Serverless (if using Bedrock KB + Agent path): there is a minimum charge even when idle. Plan your ingestion jobs and test cycles accordingly.

**Take 3 cost screenshots (required in Evidence Pack):**
1. Wednesday EOD — after Day 1 deploy
2. Thursday EOD — after Day 2 deploy + monitoring setup
3. Friday morning — before demo slot (the "official" cost record)

**Cost tiers for your information:**
- <$30 total + clean teardown + Criterion II ≥ 4.0 + Criterion III ≥ 4.0: eligible for the cost-discipline bonus (+0.25). **Quality gate** — cheap deployment with weak architecture/QnA does NOT qualify.
- $30-60 total: strong discipline, well within the $100 cap
- $60-100: OK — within ceiling but watch your burn rate
- $100+: HARD CAP exceeded — Criterion IV capped at 3, and your trainer will investigate cost drivers during QnA

---

## Common Mistakes — Avoid These

**1. "We'll set up the Budget alert later"**
Do it before deploying any paid service. If NAT Gateway runs for 24 hours before you realize, that's $1.50 gone with no warning. The alert is your early-warning system.

**2. "We'll enable Bedrock model access on Wednesday morning"**
Enable it on prep day (Monday or Tuesday). Propagation takes 5-10 minutes. Brand-new accounts may take longer. Discovering this Wednesday at 9:30 wastes an hour.

**3. "We'll record the demo video on Friday morning"**
Record it Thursday afternoon. Friday morning you will be too stressed and too rushed. The video is your insurance policy for a live demo failure.

**4. "We left NAT Gateway running overnight"**
At $1.50/day, two nights of NAT Gateway = $3. If you don't genuinely need it (most groups don't), use VPC endpoints for S3 and DynamoDB instead. Or put everything in the public subnet with strict security groups.

**5. "Only one person knows the AWS console password"**
Create IAM users for each team member with appropriate permissions. If the one person with the password is absent or has a laptop issue on Friday, your demo fails. This is a single-point-of-failure failure.

**6. "Our Evidence Pack is just screenshots"**
Screenshots without explanations score lower. Add 1-2 lines per screenshot: what does this show, why does it matter, what configuration choice does it prove. Two minutes of writing per screenshot makes a meaningful difference to your Criterion IV score.

**7. "We're using Bedrock Sonnet in our dev loop"**
Model price spread is huge — Claude Sonnet is ~15x Haiku, Mistral Large is ~16x Llama, etc. Always benchmark the cheapest reasonable option FIRST on your task. A test loop running an expensive model overnight can hit $20+ before you notice — Cost Anomaly Detection should catch it within 30-60 min.

**8. "We picked DynamoDB because it sounds cool" (or any service for any reason other than fit)**
Every service choice will be questioned during QnA. "We picked Cognito because we had to" is not an answer — it tells the trainer you do not understand your own architecture. For each of your 7 mandatory capability domains, be ready to say: "We chose [service] for [capability] because [specific reason tied to our use case] — the alternative was [other service] but we rejected it because [trade-off]." This is what separates a score 3 architecture from a score 5.

**9. "We're going to do all three optional capabilities"**
You have 16 hours across two days. Getting 7 mandatory capabilities solid takes 12-14 hours for an organized team. One optional capability takes 2-3 hours. One bonus path takes 1-2 hours. Trying all three optional capabilities means doing all three poorly and arriving at Friday with nothing demonstrable beyond the mandatory baseline. Pick one optional capability at Wednesday sign-off and commit to it. The rule: 1 done well > 3 half-done. This applies to bonus paths too.

**10. "Our React frontend needs to be ready before we touch the backend"**
Backend is 40% of your score. Frontend styling is 0% of your score. A plain HTML form with a file input and a submit button satisfies capability #1. If your team has spent all of Wednesday afternoon on a React frontend and your API endpoint does not exist yet, you are on the wrong path. Ship the ugly HTML form. Get the backend working. Style later only if you have hours to spare Thursday afternoon.

**11. "We need proper Cognito with email verification before we can demo"**
Capability #7 requires IAM least-privilege roles for all services. User-facing auth — Cognito, signed URLs, or hardcoded test credentials — is your team's choice. A hardcoded test user (`username: demo, password: demo123`) is enough to satisfy the demo requirement. Do not spend 3+ hours on Cognito's email verification, account recovery, and custom UI pages when that time could go to your AI feature.

**12. "The code is a mess — we should clean it up before continuing"**
Trainers interact with your URL, not your code. A well-structured codebase with a broken demo scores zero on Criterion IV. A messy single-file Lambda with a working demo scores well. Refactor in Phase 2 if you make it. Right now: ship.

**10. "We'll delete everything next week"**
Teardown deadline is Sunday 1 June, end of day. Resources left running continue billing your personal account indefinitely. Delete in order: CloudFormation stacks (if used) → Lambda → API Gateway → RDS → S3 (empty buckets first) → Cognito → VPC (last — delete subnets, IGW, route tables, then VPC). Take a screenshot of the empty Cost Explorer on Monday 2 June and commit it to your repo as `docs/teardown_confirmed.png`.

---

## What Evaluation Looks Like

| Criterion | Weight | What Matters |
|-----------|--------|-------------|
| Pitch + Vision | 10% | Can you explain who the user is, what problem you're solving, and why AI? |
| Architecture | 20% | All 7 mandatory capabilities in diagram with justified service choices. 2-3 genuine trade-offs named. Score 4 = 7 mandatory solid. Score 5 = 7 mandatory + 1 optional capability done well shown in diagram. |
| Individual QnA | 30% | Can you explain your group's decisions without help from your team? |
| Working Deployment + Evidence | 40% | All 7 mandatory capabilities demonstrable. Evidence Pack complete. Score 4 = 7 mandatory solid + complete Evidence Pack. Score 5 = 7 mandatory + 1 optional capability demonstrably working. |

Bonus paths (choose at most 1-2, done well):
- Custom domain + HTTPS via Route 53 + ACM
- CI/CD pipeline (GitHub Actions or CodePipeline)
- Full IaC in your chosen tool (CloudFormation / CDK / Terraform / SAM / Pulumi / AWS Cloud Control) — can teardown and redeploy in 5 min
- Bedrock Guardrails configured (content filter, PII redaction, topic denial)
- Real users (5+ external people tested your app + feedback documented)
- Multi-region failover (hard — only attempt if you are ahead of schedule Thursday noon)
- Cost <$30 total + clean teardown (track this throughout — bonus is awarded retroactively after Mon 2/6 teardown screenshot)

One bonus done well beats three bonuses done halfway. The trainer verifies bonuses via Evidence Pack documentation and live demo.

---

## Teardown Checklist — Do This by Sunday 1 June EOD

Delete resources in this order (dependencies matter):

1. Delete CloudFormation stacks (if you used IaC — this deletes most resources automatically)
2. Delete Lambda functions
3. Delete API Gateway stages and APIs
4. Delete Bedrock Agent and Knowledge Base
5. Delete RDS instances (snapshot optional — skip if you don't need the data)
6. Empty S3 buckets (must empty before deleting)
7. Delete S3 buckets
8. Delete Cognito User Pool
9. Delete KMS Customer Managed Keys (schedule deletion — 7-day minimum waiting period)
10. Delete CloudWatch dashboards, alarms, log groups
11. Delete VPC last: subnets → security groups → NAT Gateway → Internet Gateway → route tables → VPC
12. Verify in Cost Explorer on Monday 2 June morning that no charges are accruing
13. Take a screenshot of the near-zero Cost Explorer view
14. Commit screenshot to repo as `docs/teardown_confirmed.png`

That screenshot is your final deliverable for Phase 1.

---

## Key AWS Services for Capstone Reference

| Service | What It Does | Why It Matters in W7 |
|---------|-------------|----------------------|
| Amazon Cognito | User pools, sign-up/sign-in, JWT tokens | Auth layer — handles login so you don't build it yourself |
| Amazon Bedrock (foundation model — your choice) | LLM inference — generate text from a prompt | Core AI capability. Compare $/1M tokens across Claude/Llama/Titan/Cohere/Mistral BEFORE locking in. Document choice + measurement in §6.5. |
| Bedrock Knowledge Base | RAG — ingest documents into vector store, query by similarity | Makes AI answer questions about YOUR documents, not just general knowledge |
| Bedrock Agent | Orchestration layer — routes user intent, calls KB, calls Lambda tools | Connects KB to your application logic; enables multi-turn conversation |
| AWS Lambda | Serverless compute — runs code on demand, no servers | Your application backend — handles API logic, calls Bedrock, reads/writes DB |
| Amazon API Gateway | HTTP/REST API front-door — routes requests to Lambda | Public endpoint your frontend calls; handles Cognito auth validation |
| Amazon DynamoDB | NoSQL, fully managed, pay-per-request | Low ops overhead — good for session data, user profiles, simple data models |
| Amazon RDS (PostgreSQL) | Relational DB, managed, single-AZ for hackathon | Good for relational data models — slightly more complex setup than DynamoDB |
| Amazon S3 + KMS CMK | Object storage with customer-managed encryption | Document storage (KB source) + static frontend hosting + encrypted at rest |
| Amazon CloudFront | CDN — serves S3 frontend globally via HTTPS | Solves the HTTPS requirement for your frontend URL |
| Amazon CloudWatch | Metrics, alarms, dashboards, log queries | Monitoring layer — required for full Criterion IV score |
| AWS Budgets | Cost alerts when spend exceeds threshold | Required — Budget alert at $80 (80% of $100 HARD CAP) with email confirmed before Day 1 deploy |
| Cost Anomaly Detection | ML-based cost spike detection | Catches runaway costs faster than Cost Explorer (near real-time) |
| Amazon VPC | Private network — subnets, SGs, routing | Network isolation layer — required; keep it simple (skip NAT GW if possible) |