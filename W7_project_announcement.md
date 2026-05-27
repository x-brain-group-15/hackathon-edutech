---
week: 7
title: "W7: Capstone Hackathon — Ship Production-Ready AI in 48 Hours"
audience: students
release: "Wed 2026-05-28 09:00"
deadline: "Fri 2026-05-30 09:00 — slides + repo + live URL"
---

# W7: Capstone Hackathon
## Ship Production-Ready AI in 48 Hours

> May 28–31, 2026 | Personal AWS Account | $100 HARD CAP | Demo Day: Fri–Sat 30–31/5 (2 days, presentation-focused)

---

## The Challenge

Six weeks ago you drew a box labeled "frontend," another labeled "backend," and a third labeled "database," and called it an architecture. Since then you have filled every one of those boxes with real services, real IAM policies, real network rules, and real data flowing end to end. You chose a database paradigm and justified it. You built a retrieval pipeline on Bedrock. You hardened a VPC. You wired CloudWatch alarms that fire on actual data points. You tagged resources so that Cost Explorer can tell you exactly what your application costs. That is six weeks of compounding skill.

W7 is the test of whether those skills are yours — not the workshop account's. This week there is no instructor-managed environment to fall back on. No account that resets if you break something. No free infrastructure courtesy of the training program. You are building on personal AWS accounts, paying real money, and you have 48 hours to ship a live, public, production-ready AI SaaS platform. Then you will stand in front of the room on Friday, give a trainer your URL, and watch them interact with your system in real time.

That sentence deserves to sit for a moment. A trainer will open your URL on their browser — not a screenshot of your URL, not a recording — and they will log in, upload a file, and watch your AI process it. If it works, it works. If the demo URL returns 502 Bad Gateway at 09:00 Friday because someone forgot to check that the Lambda health response passes after cold start, that is visible to everyone in the room. If the budget alert you set never fired because you subscribed to the SNS topic but forgot to confirm the email, that is a gap in your evidence. If the only team member with console access calls in sick Thursday night, that is a single point of failure no one planned for.

Build toward one sentence: "Trainer, click this link. Log in with this test account. Upload this sample file. Watch the AI process it. That is our system. We built it in 48 hours, on our own AWS account, for under $100." That sentence is the bar. Every decision you make between Wednesday morning and Friday 09:00 should be judged against whether it gets you closer to saying it confidently.

---

## What's Different from W1-W6

| Aspect | W1-W6 Workshop | W7 Capstone |
|--------|---------------|-------------|
| AWS account | Trainer-managed, resets weekly | Personal account — real billing |
| Cost | $0 to students | Real bill, $100 hard cap (must not exceed) |
| Infrastructure teardown | Automatic (account reset) | Manual — delete by Sun 1/6 EOD |
| Topic | Group chose domain in W1 | Trainer-given (3 domain options) |
| Build window | 5 days per week | 48 hours (Wed-Thu build) |
| Deployment | Optional or partial in early weeks | Mandatory — public HTTPS URL required |
| Carry-forward | Architecture, design decisions | W1-W6 skills only (not AWS resources) |
| Support | Trainers guide and teach | Trainers triage blockers, not write code |

**What carries forward:** Everything you know. Nothing you deployed. Workshop accounts are gone. What you bring into W7 is the ability to think in layers — compute, storage, network, monitoring, cost — and the hands-on knowledge of how to wire each one correctly.

---

## The Project — Choose Your Domain

Every group builds an AI-Powered SaaS Platform. The technical stack is identical regardless of domain. What differs is the user story and the type of documents your system processes.

---

### Domain A — EduTech: "AI Study Buddy"

**Tagline:** Upload your lecture slides. Get a study guide, flashcard set, and quiz in seconds.

**Target users:** University students, self-learners, exam-prep candidates.

**User stories:**
- Upload a 40-slide lecture PDF and receive a one-page summary with the five most testable concepts.
- Ask the system a question about the topic and get an answer with citations back to the specific slide.
- Request a 10-question multiple-choice quiz generated from the uploaded notes.
- Track which topics have been studied this week in a personal dashboard.

**Pick this domain if** your team enjoys prompt engineering challenges and wants a demo that is immediately relatable to any interviewer who has ever been a student.

#### 🎯 Core Challenge — Document Intelligence

The hard problem is NOT "store + retrieve PDF". It is: **extract structured information from unstructured slide content** — tables, figures, code blocks, equations, multi-column layouts, image-based slides — and then make it retrievable at the granularity students actually ask questions at.

What we expect you to demonstrate on Friday:
- A document where text extraction is non-trivial (a slide deck with at least one table, figure caption, or scanned/image page)
- A measured retrieval quality on YOUR content (precision@k or response-relevance Likert on 5+ probe questions)
- A conscious chunking decision with evidence (chunk size trade-off, semantic vs fixed)
- A failure mode you discovered and mitigated (be specific — name a query that broke and what you changed)

⚠️ **Service bias warning — "PDF" does NOT mean "Textract by default":**

| Path | When it wins | When it loses |
|------|-------------|---------------|
| **Textract** | Tables + forms heavy; scanned PDFs | Pure-text PDFs (overpay); cost per page |
| **Bedrock Anthropic Vision (Claude)** | Figure/diagram heavy; multi-modal slides | Expensive per page; high latency |
| **pypdf / pdfplumber + tesseract** | Text-heavy PDFs; runs in Lambda; free | Weak on image PDFs; no table awareness |
| **Comprehend** | Post-OCR entity/key-phrase extraction | Not OCR itself — pairs with another layer |
| **Hybrid** | Text density threshold → fallback path | More moving parts |

Trainers reward **less obvious paths justified with measurement**. "We used Textract because default" → low Criterion II/III. "We used pypdf first, fallback to Textract when text density < 100 chars/page, measured 73% pypdf success on our 30-doc sample, saved $0.0011 per upload" → high Criterion II/III.

#### 🌍 Real-world parallels

Quizlet AI · Khanmigo (Khan Academy AI tutor) · Coursera Coach · Google NotebookLM · Anthropic Claude for Education.

Ask yourself during build: *"If a Khanmigo engineer reviewed our architecture, what would they immediately point out as wrong/missing/naive?"* Document the answer in Evidence Pack §6.5.

---

### Domain B — FinTech: "AI Money Coach"

**Tagline:** Upload your bank statement. Understand exactly where your money went.

**Target users:** Individuals managing personal budgets, small business owners tracking expenses.

**User stories:**
- Upload a three-month PDF bank statement and receive a categorized breakdown: food, transport, subscriptions, unclassified.
- Ask "How much did I spend on food last month?" and get a specific answer with the contributing line items.
- Receive a budget recommendation based on spending pattern and a savings target.
- Set a monthly cap for a category and get an alert when transactions push past it.

**Pick this domain if** your team is comfortable with financial data, enjoys parsing messy CSV inputs, or wants a demo that resonates with business stakeholders.

#### 🎯 Core Challenge — Dirty Input Classification

The hard problem is NOT "call LLM on bank descriptions". It is: **bank descriptions are cryptic, ambiguous, and routinely sit at the boundary of multiple categories**:

- `VINMART HCM 04` — Food (groceries), Shopping (household), or both?
- `T1908 GRAB CITY` — Transport (ride) or Food (GrabFood)?
- `FT0024112501 ID:0001` — total opacity. What now?
- `MACBOOK PRO 14 SHOPEE` — Shopping for personal? For work? A subscription tier?

What we expect you to demonstrate on Friday:
- Confidence scoring (model says "Food" — how confident? what threshold triggers human review?)
- Ambiguity handling (user-correctable categories, multi-label support, or review queue)
- A measured classification accuracy on YOUR sample (precision/recall per category on 30+ labeled rows, simple confusion matrix is enough)
- A named failure case + your concrete fix (e.g., "FT0024..." opaque codes → escalate to manual review with confidence < 0.6)

⚠️ **Service bias warning — "Classify" does NOT mean "Bedrock by default":**

| Path | When it wins | When it loses |
|------|-------------|---------------|
| **Bedrock zero-shot** | Fastest to build; reasonable for clear descriptions | Weakest on cryptic codes (~$0.50/1K txns) |
| **Bedrock few-shot (5-10 examples)** | Big accuracy boost with small prompt cost | Prompt context grows → cost per call up |
| **Comprehend Custom Classifier** | Cheaper inference at scale; train on labeled data | Needs labeled training data upfront |
| **Rule-based + LLM hybrid** | Regex for known prefixes (GRAB → Transport); LLM for ambiguous | More code paths to maintain |
| **RAG over user's labeled history** | Personalized to user's correction pattern over time | Cold-start problem for new users |
| **Human-in-the-loop review queue** | Recovers from low-confidence cases; learns over time | Slower path; UX consideration |

Trainers reward "Bedrock few-shot prompt + confusion matrix on 30 labeled rows + 2 named failure cases with fixes" over "we called Bedrock, it works".

#### 🌍 Real-world parallels

Money Lover (VN) · Spendee · YNAB · Cake by VPBank ("Cake AI") · Plaid (data layer) · Monzo (UK) · Revolut spending insights.

Ask yourself during build: *"If we showed our categorizer to a Cake AI engineer, what edge cases would they bring up that we haven't handled?"* Document the answer in Evidence Pack §6.5.

---

### Domain C — ProductivityTech: "AI Document Hub"

**Tagline:** Upload any contract, report, or policy doc. Search and ask questions across all of them.

**Target users:** Legal teams, compliance officers, knowledge workers managing large document libraries.

**User stories:**
- Upload 20 contracts and ask "Which ones have a termination clause shorter than 30 days?" and receive a filtered list.
- Ask the system to summarize the key obligations in a specific agreement.
- Upload a new policy document and have it immediately searchable alongside all prior documents.
- Different user accounts see only their own document collections — tenant isolation enforced.

**Pick this domain if** your team is interested in enterprise SaaS patterns, multi-tenancy, or building something that mirrors real legal-tech and compliance-tech products.

#### 🎯 Core Challenge — Multi-tenant Freshness + Document Confusion

Two genuinely hard problems live in this domain:

1. **Document confusion** — when 2 contracts in the same tenant use similar language, the AI may cite the wrong contract's clause as evidence. Tenant_id metadata filter is necessary but NOT sufficient.
2. **Freshness / staleness** — contracts get amended, policies get versioned. How do you guarantee the AI never returns last quarter's version as authoritative when a new one was uploaded yesterday?

What we expect you to demonstrate on Friday:
- A versioning scheme (S3 versioning / DDB version field / KB metadata tags)
- A confusion-mitigation strategy (aggressive metadata filter, citation strictness, per-doc score threshold)
- A measurement: how often does retrieval pick the wrong document on YOUR sample? Sample 20 queries, manually verify, report wrong-doc rate
- A staleness detection mechanism (last_updated metadata, re-ingestion schedule, version drift alert)

⚠️ **Service bias warning — "Multi-tenant docs" does NOT mean "Bedrock KB + DynamoDB by default":**

| Path | When it wins | When it loses |
|------|-------------|---------------|
| **S3 versioning + KB re-ingest** | Simple, AWS-native | Re-ingestion cost; tenant_id metadata required separately |
| **DynamoDB version field + GSI** | Cheap, fine-grained | Hard to sync to KB metadata; manual eviction logic |
| **EventBridge scheduled re-sync** | Predictable refresh cadence | Staleness window = sync interval |
| **Document hash diff** | Re-ingest only when content actually changed; saves no-op syncs | More logic to test |
| **Per-tenant retention policy** | Audit-friendly; legal compliance | Adds operational complexity |

Trainers reward groups that **named the wrong-document failure mode** and showed concrete mitigation. "Bedrock KB with tenant filter" is the starting line, not the finish line.

#### 🌍 Real-world parallels

Harvey AI (legal) · Hebbia · Ironclad (contracts) · Glean Workspace · Microsoft Copilot for M365 · Cohere North.

Ask yourself during build: *"If a Harvey AI engineer audited our system, what would they say about how we handle wrong-document returns or stale contracts at 10K docs/tenant?"* Document the answer in Evidence Pack §6.5.

---

## Capabilities — 7 Mandatory + 3 Optional + Pre-flight Safety

Your system is built in layers. The 7 mandatory capabilities are non-negotiable — every group must demonstrate all of them on Friday. The 3 optional capabilities are bonus opportunities that push your Likert scores higher. The pre-flight safety items are required baseline checks that must be verified by Wednesday sign-off.

Which specific AWS service implements each capability is your team's decision — that is intentional. On Friday, trainers will ask "why did you pick this service for this capability?" A strong answer connects to trade-offs you discussed in W1-W6. A weak answer is "we used what we knew" with no reasoning.

### 7 Mandatory Capabilities (every group must demonstrate)

| # | Capability | What your system must do | Service options taught W1-W6 |
|---|-----------|--------------------------|------------------------------|
| 1 | **User-Facing Entry** | Public HTTPS entry — static frontend hosting AND/OR the API endpoint that compute sits behind. **EDGE/ENTRY layer, NOT compute.** | **Static hosting:** S3+CloudFront · Amplify hosting · ALB+S3 origin · CloudFront with custom origin. **API entry:** API Gateway (HTTP/REST) · ALB · Lambda Function URL · AppSync · App Runner endpoint |
| 2 | **Application Compute** | Where backend code **RUNS** — processes requests, calls AI, executes business logic. **SEPARATE from the API endpoint in #1.** | Lambda · EC2 · ECS/Fargate · App Runner · Step Functions · AppSync resolver code · self-hosted on EC2 |
| 3 | **AI / ML Feature** | At least one intelligent capability working end-to-end | Bedrock (KB+Agent OR InvokeModel), Comprehend, Rekognition, Textract, SageMaker, etc. |
| 4 | **Data Persistence** | Stores and reads user state across sessions | RDS, Aurora, DynamoDB, ElastiCache, DocumentDB, Neptune, self-hosted on EC2, etc. |
| 5 | **Object Storage** | Files, blobs, and unstructured data | S3 (any class) |
| 6 | **Network Foundation** | Resources isolated — DB not public-facing | VPC + subnets + Security Groups + (optional) NAT/VPC Endpoints |
| 7 | **Identity & Access (baseline)** | IAM least-privilege roles for all services. User-facing auth is optional — choose IAM-only access OR Cognito User Pool OR signed URLs | IAM roles (required), Cognito, signed URLs, custom JWT, etc. |

#### Common entry+compute pairings — each side counts as a SEPARATE mandatory slot

| Pattern | Mandatory #1 (edge entry) | Mandatory #2 (compute) |
|---------|---------------------------|------------------------|
| ALB + EC2 | ALB | EC2 |
| ALB + ECS/Fargate | ALB | ECS/Fargate |
| API Gateway + Lambda | API Gateway | Lambda |
| Lambda Function URL | Lambda Function URL (built-in HTTPS) | Lambda (same one) |
| App Runner | App Runner (built-in HTTPS) | App Runner (same one) |
| Amplify hosting + API Gateway + Lambda | Amplify + API Gateway | Lambda |
| AppSync | AppSync GraphQL endpoint | AppSync resolver / Lambda resolver |
| CloudFront + ALB + EC2 | CloudFront + ALB | EC2 |

Lambda Function URL, App Runner, AppSync collapse #1 and #2 into one resource — fine, but articulate WHICH role the resource plays during Architecture Walkthrough (the trainer will ask).


### 3 Optional Capabilities (bonus — drive higher scores, partial credit)

These are not required to pass. Pick ONE and do it well — one done well beats three half-done.

| # | Capability | No mandatory minimum | What earns bonus credit |
|---|-----------|---------------------|------------------------|
| 8 | **Full Observability** | No minimum required | Dashboard + at least 1 custom metric (PutMetricData) + at least 1 alarm in OK/ALARM state (not INSUFFICIENT_DATA) + at least 1 saved Log Insights query |
| 9 | **Advanced Cost Insights** | Pre-flight budget alert is required (see below) | 3 daily Cost Explorer screenshots + breakdown observation + cost-per-feature analysis + Cost Anomaly Detection alert demo |
| 10 | **Advanced Security** | IAM least-privilege already mandatory in #7. **Pick ONE area + go deep — no specific service forced.** | **Encryption at rest:** KMS CMK + rotation · KMS AWS-managed key · application-layer encryption (libsodium / age / etc.). **Encryption in transit:** TLS 1.2+ everywhere · certificate lifecycle (ACM rotation) · mutual TLS. **Audit & detection:** CloudTrail trail + Config rules · Security Hub · GuardDuty · Inspector. **Secrets:** Secrets Manager + rotation · Parameter Store SecureString · sealed Vault pattern. **Network security:** WAF rules · Shield · Security Group strictness · VPC Flow Logs analysis. Demonstrate WITH measurement (what's encrypted/audited, rotation cadence, alarm trigger count, blocked attempts). |

**Scoring distinction:** Optional capabilities (8-10) push your baseline Likert scores (Architecture and Deployment criteria) higher. Bonus paths A-H below are separate — they add up to +0.5 on top of your final score. Focus on 7 mandatory rock-solid first, then pick one optional capability to do well, then consider bonus paths if time allows.

### Pre-flight Safety Requirements (required before deploying any paid infrastructure)

These must be verified at the Wednesday architecture sign-off. Missing any one = group must fix before deploying expensive resources.

- Personal AWS account active with MFA on root
- Budget Alert at $80 (80% of $100 cap) with confirmed SNS email subscription
- Cost Anomaly Detection enabled
- Tagging strategy applied: `Project=W7Capstone`, `Team=G<N>`, `Owner=<name>`, `Environment=hackathon`
- Bedrock model access enabled — request access for the foundation model(s) your team plans to use (Claude family / Llama / Mistral / Titan / Cohere / Jurassic / etc.) + an embeddings model if your AI feature is RAG-based. Pick AFTER comparing prices.

**Required production artifacts (regardless of which services you choose):**
- Public HTTPS URL that loads in a trainer's browser
- Working AI feature (real model invocation, observable result in the UI)
- Persistent state (write something Thursday, read it back Friday in a fresh session)
- All 7 mandatory capabilities covered with justified service choices

**Bedrock note:** Use only what was covered in W3-W4. Do not pivot to external LLM APIs. If you learned it before W7, you can use it. If not, focus on what you know.

---

## Hackathon Quality Bar — Ship, Don't Polish

This is a 48-hour hackathon, NOT a production launch. Code is allowed to be hackathon-level. Architecture decisions and a working LIVE happy-path demo are what we grade — not code beauty.

### What IS graded (must be solid)

| Graded | |
|--------|--|
| Architecture decisions + service rationale ("why this service for this capability?") | |
| 7 mandatory capabilities present and working | |
| Live URL functional for the happy path | |
| AI feature produces real, observable output | |
| Persistent state demo (write then read back across sessions) | |
| Evidence Pack documentation (screenshots, decisions, cost) | |
| Cost discipline (Budget alert + under $100 hard cap + tagging) | |

### What is NOT graded (hackathon-level is fine)

| NOT graded — do not spend time on this | |
|-----------------------------------------|--|
| Code quality or structure (single-file Lambda is fine) | |
| Frontend polish, design, or styling (a basic HTML form is fine) | |
| Comprehensive error handling (let errors throw — log to CloudWatch) | |
| Unit tests, integration tests, code coverage | |
| Edge case handling (happy path is enough) | |
| Performance optimization | |
| Production-grade auth flow (hardcoded test user is fine for the demo) | |
| Mobile responsive design | |
| Beautiful slides (functional is better than pretty) | |

### Real-world parallel

TechCrunch Disrupt, AWS GameDay, AngelHack, and Y Combinator hackathons all explicitly say "ship, don't polish." Code quality is irrelevant — what matters is "did you build something that demos."

### Common over-engineering traps to AVOID

- Building a beautiful React UI when a single HTML form would work the same in 30 minutes
- Setting up Cognito with full signup/login/password reset — use IAM-only auth or a hardcoded test user instead. Cognito is OPTIONAL per capability #7.
- Writing comprehensive error handling for edge cases — just throw and log to CloudWatch
- Refactoring code mid-hackathon ("we should split this Lambda into three" — NO, ship first, refactor in W8 if you survive)
- Spending 2+ hours on slide design when a simple template works
- Writing unit tests during the hackathon

### What "ship" means concretely

By Friday, your team should be able to do this in one minute live:

> "Trainer, click this URL [send link]. The page loads. Click 'Try it'. Type 'hello'. Press submit. Wait 2 seconds. AI response appears on screen. The same response is now saved in our database — we can show you the row. That's our system."

That is the bar. Architecture and rationale on top of that drive higher tier.

---

## Cost Constraints — $100 HARD CAP (must not exceed)

Your personal account, your real bill. Cost discipline is not optional — it is graded and you will be asked about it on Friday.

### Pre-flight safety setup (complete before Wednesday architecture sign-off — not optional)

These are verified by your trainer or mentor before you deploy any paid infrastructure. Missing any item = group must fix before sign-off is granted.

- [ ] MFA enabled on AWS root account
- [ ] AWS Budget created at $100 total, alert threshold at $80 (80%) via SNS — confirm the subscription email before you build anything else
- [ ] Cost Anomaly Detection enabled at the account level (free, ML-based, takes two minutes)
- [ ] Tagging strategy applied to every resource: `Project=W7Capstone`, `Team=G<N>`, `Owner=<name>`, `Environment=hackathon`
- [ ] Bedrock model access enabled — request foundation model(s) team chose (Claude / Llama / Mistral / Titan / Cohere / etc.) + embeddings model if RAG-based
- [ ] Cost Explorer screenshot taken at Day 1 EOD, Day 2 EOD, and Friday morning pre-demo

### Cost discipline tiers

| Total spend by Friday | Status | What happens |
|-----------------------|--------|--------------|
| Under $30 + clean teardown **AND** Criterion II ≥ 4.0 **AND** Criterion III ≥ 4.0 | Bonus eligible (+0.25) | Cost + quality gate. Cheap deployment with weak architecture/QnA does NOT qualify. Document trade-offs in Evidence Pack §6.5 (Measurement & Decisions). |
| Under $5 total **AND** Criterion II < 4.0 | UNDER-DEPLOYMENT FLAG | Trainer follow-up required. Single Lambda + DynamoDB at $3 with no observability / no security / no real challenge tackled is NOT cost discipline — it's not deploying enough. Bonus denied, II capped at 2.5. |
| $30-60 + clean teardown | Strong cost discipline | Cited positively in Part 4 |
| $60-100 | OK within cap | Explain your top 3 cost drivers |
| Over $100 | HARD CAP EXCEEDED | Criterion IV capped at 3 — cost discipline failure |

### Recipe to stay under $100

The biggest cost traps are services running quietly in the background. None of these individually are catastrophic at the $100 cap, but they add up:

- **t3.micro / db.t3.micro** — free-tier eligible, sufficient for demo workloads
- **Cheapest sufficient model in dev — compare $/1M tokens BEFORE locking in.** Examples: Claude Haiku $0.25/$1.25 in/out · Sonnet $3/$15 · Llama 3.1 70B $0.30/$0.30 · Titan Text Express $0.30/$0.40 · Cohere Command R $0.50/$1.50 · Mistral Large $4/$12. Upgrade for demo only if quality differential is **measured**, not guessed. Document the comparison in Evidence Pack §6.5.
- **Single-AZ RDS** — Multi-AZ doubles database cost. Skip it for the hackathon.
- **NAT Gateway costs $1.08/day** — if your Lambda only calls AWS services, use VPC endpoints (Gateway endpoint for S3/DynamoDB, Interface endpoint for Bedrock) instead of a NAT Gateway. If you must use NAT, delete it Thursday EOD.
- **KMS: one CMK maximum** — each Customer Managed Key costs $1/month prorated. One key is fine. Five is not.
- **Delete unused resources daily** — an idle EC2 from a Wednesday experiment running through Friday is wasted money.

### Teardown mandate

By Sunday 1/6 EOD, every resource your group created must be deleted. Take a Cost Explorer screenshot Monday 2/6 as confirmation. Commit `docs/teardown_confirmation.md` to your repo with the list of deleted resources. Failure to teardown means continued personal billing — that is your money, not the program's.

---

## Day-by-Day Plan

> 📝 **Important — Day 1 / Day 2 breakdown below is a SUGGESTED checkpoint rhythm, not a mandate.**
>
> If your team already has its own 48-hour plan, follow that — split the work however you want (sprint at night, work in shifts, parallelize differently, do AI integration on Wed and infra on Thu). **The only hard deadline is Friday 09:00 with a working URL + presentation ready.**
>
> The Day 1 / Day 2 timeline below is here so groups WITHOUT a plan have a default rhythm to follow + so trainers know where to spot-check. Treat it as a checkpoint guide, not a contract.

### Wednesday 28/5 — Day 1 (suggested): Architecture Lock + 7 Mandatory Capabilities

The hardest mistake on Day 1 is starting to code before the architecture is agreed. Spend the first 90 minutes planning. Everything after that is faster. Wednesday is purely about getting all 7 mandatory capabilities deployed and connected — do not attempt optional capabilities today.

| Time | Goal |
|------|------|
| 09:00-10:30 | Architecture lock — domain confirmed, diagram drawn, roles assigned, service choices agreed for all 7 mandatory capabilities |
| 10:30-11:00 | Pre-flight safety verification — Budget alert + Cost Anomaly Detection + tagging + confirm SNS subscription + Bedrock model access |
| 11:00-13:00 | Foundation — VPC, subnets, security groups, S3 buckets, IAM roles (mandatory #5, #6, #7) |
| 13:00-14:00 | Break + check current cost |
| 14:00-16:30 | Core services — API endpoint [#1 edge: API Gateway / ALB / Function URL / etc.] + compute [#2: Lambda / EC2 / Fargate / etc.] + database [#4] in private subnet |
| 16:30-17:00 | Happy path test: does the API respond? Does the database write/read work? Can Bedrock return something? |
| 17:00 | Day 1 cost screenshot + commit architecture diagram to repo |

**Day 1 success state:** API responds. Database is reachable from Lambda. Bedrock InvokeModel returned at least one response in CloudWatch logs. All 7 mandatory capability slots are filled with a named service. No optional capability work yet.

### Thursday 29/5 — Day 2 (suggested): AI Integration + Polish + 1 Optional Capability

Day 2 is where groups that over-scoped Day 1 start cutting. Make your scope decisions by 14:00 — not at 22:00.

**Time budget reality:** You have roughly 16 hours across Wed-Thu. Getting all 7 mandatory capabilities solid takes about 12-14 hours for an organized team. Adding one optional capability takes about 2-3 hours. Adding one bonus path takes about 1-2 hours. Do not try all three optional capabilities — pick one and do it well.

| Time | Goal |
|------|------|
| 09:00-09:30 | Review Day 1 state — what works, what doesn't, what gets cut |
| 09:30-12:00 | Bedrock integration — KB sync + Agent OR InvokeModel pipeline wired end-to-end (mandatory #3) |
| 12:00-13:00 | Break + check current cost |
| 13:00-14:30 | Pick ONE optional capability + tackle: Full Observability (dashboard + custom metric + alarm) OR Advanced Cost Insights (3 screenshots + analysis) OR Advanced Security (your chosen area: encryption / audit / secrets / network) |
| 14:30-15:30 | Evidence Pack — write sections 1-7 now, not Thursday night |
| 15:30-16:30 | Demo rehearsal — full end-to-end walkthrough twice. Find the failure modes before Friday finds them. |
| 16:30-17:00 | Day 2 cost screenshot + slides finalized + repo pushed |

**Day 2 success state:** Trainer can click your URL, upload a file, see the AI result. One optional capability is demonstrably working. Evidence Pack is 80% written. Demo has been run at least twice.

### Fri–Sat 30–31/5 — Demo Day

Slides, repo, and live URL ready by 09:00. Use the morning before your slot to rehearse on a fresh browser with cleared cookies.

---

## What Friday Part 2 Looks Like — Showing Your Work

Friday Part 2 (Architecture Walkthrough) is where you walk the trainer through what you built. The walkthrough structure:

**Part 1 (first): 7 Mandatory Capabilities — trainer verifies baseline**
The trainer checks all 7 mandatory capabilities are working. Show each one — the live URL, the AI responding, the database reading back state, the network isolation (DB not public-facing), the S3 bucket, the IAM roles scoped to least-privilege. All 7 must be demonstrable. This is the baseline for scoring.

**Part 2 (second): Optional capability attempted**
After the 7 mandatory, tell the trainer which optional capability your group attempted (Full Observability, Advanced Cost Insights, or Advanced Security). Show what you built. Partial progress counts — a custom metric that is publishing data but no alarm yet is worth more than nothing. One optional done well drives your Likert scores higher than three half-done optionals.

**The non-negotiables every group must show:**

**1. Live URL (HTTPS, accessible from trainer's browser)**
Not localhost. Not a screenshot. A public URL that loads in any browser with no VPN or special setup. CloudFront gives you HTTPS on the default `*.cloudfront.net` domain for free.

**2. Working AI feature with real Bedrock invocation**
Not the Bedrock playground. A real API call from your application — through a Knowledge Base retrieve-and-generate, an Agent invocation, or a direct InvokeModel call — with an observable result in the UI. The trainer will ask which model, which parameters, and what the response structure looks like.

**3. Persistent state — write then read back**
Write something on Thursday. On Friday, access it in a fresh session and confirm it is still there and readable. State that does not survive a session boundary is not persistent state.

**4. Network isolation — DB not public-facing**
Show the trainer that your database is in a private subnet with a security group that only allows the compute layer (Lambda SG or EC2 SG) to connect. A database with inbound `0.0.0.0/0` is a security failure visible in 30 seconds.

**5. Cost discipline evidence via Cost Explorer**
Open Cost Explorer, filter by your `Team=G<N>` tag, show the breakdown. Three daily screenshots in the Evidence Pack. A number in your slide deck: "we spent $X over two days, top drivers were Y and Z." Groups that cannot show a cost breakdown in Part 4 will face sharp follow-up questions.

---

## Worked Examples — Three Reference Architectures

These show one possible way each domain could be implemented. Your team may choose different services to cover the same capabilities — that is encouraged. On Friday, be ready to explain why your choices fit your use case better than the alternatives. Each example stays well under $100.

---

### Reference A — EduTech: "StudyBot" (one possible approach)

This example covers all 7 mandatory capabilities and demonstrates Full Observability as the chosen optional capability. This is one possible approach — your team may choose different services for any mandatory capability, and a different optional capability entirely.

**Mandatory capabilities covered (#1-7):**
[#1 UI — static] CloudFront + S3 static site → [#1 UI — API entry] API Gateway HTTP API → [#2 Compute] Lambda Python 3.12 → [#3 AI/ML] Bedrock Knowledge Base + chosen foundation model (Haiku is one option — pick after comparison) retrieve-and-generate → [#4 Data] DynamoDB session/user state. [#5 Object Storage] S3 document bucket (encryption strategy: your choice — SSE-S3 default / SSE-KMS / CMK + rotation). [#6 Network] VPC: Lambda in private subnet, DynamoDB via Gateway Endpoint, Bedrock via Interface Endpoint. [#7 Identity baseline] IAM Lambda execution role scoped to specific actions on specific ARNs.

**Optional capability attempted: Full Observability (#8)**
CloudWatch: custom metric `StudyBot/DocumentsIngested` published after each successful KB sync (PutMetricData), alarm on Lambda `Errors` metric in OK state by Thursday afternoon, Log Insights query saved to filter errors in the last hour.

Your team may choose differently — e.g., EC2 instead of Lambda, RDS instead of DynamoDB, or Advanced Security as your optional capability instead of Full Observability. The requirement is covering all 7 mandatory capabilities with justified choices plus one optional attempted well.

**Key service decisions in this example:**

| Decision | Rationale |
|----------|-----------|
| DynamoDB over RDS | User session state (quiz scores, last studied topic, quiz attempts) is always a single-key lookup by `user_id`. No JOINs, no aggregations. DynamoDB on-demand capacity handles variable load with zero provisioning. |
| Bedrock KB (RAG) over pure InvokeModel | The core feature is answering questions about a user's specific uploaded document. RAG retrieves the relevant chunks from that document and grounds the generation — no hallucination on content the user uploaded. InvokeModel without retrieval has no access to the document content at generation time. |
| CloudFront default domain | HTTPS on `*.cloudfront.net` requires zero certificate setup. Saves 30 minutes on Day 1 and $0 extra. Adopt custom domain only if going for Bonus Path C. |
| S3 Vectors as KB vector store | No minimum OCU charge unlike OpenSearch Serverless. Purpose-built for Bedrock KB. Available in us-east-1 and ap-southeast-1. |

**Data flow:**
User uploads PDF via UI → API Gateway POST `/upload` → Lambda → S3 PutObject (KMS CMK encrypted, `kb-source/{user_id}/{doc_id}.pdf`) → Lambda triggers Bedrock KB StartIngestionJob (async) → Bedrock chunks and embeds document → Stored in S3 Vectors index. On query: user types question → API Gateway POST `/query` → Lambda → Bedrock `retrieve_and_generate` with `user_id` filter → Bedrock retrieves top-K chunks from user's documents → Claude Haiku generates answer with citations → Lambda writes query event to DynamoDB (session log) → Response with answer + source citations returned to UI.

**Sample Bedrock prompt:**
```
System: You are a study assistant. Answer questions using ONLY the provided context from
the student's uploaded lecture notes. Always cite the source by document name and chunk
number. If the answer is not in the provided context, say exactly:
"This topic is not covered in your uploaded notes."
Do not make up information.

User: [Question from student]
Context: [Retrieved chunks from Bedrock KB]
```

**Estimated cost breakdown (48 hours, ap-southeast-1 Singapore list price):**

| Service | Calculation | Cost |
|---------|-------------|------|
| Lambda | 200 invocations × 512MB × 2s = 200 GB-sec | $0.004 |
| API Gateway HTTP | 500 requests | $0.001 |
| Bedrock Claude 3.5 Haiku (KB retrieve+generate) | 500K input @ $1/M + 50K output @ $5/M | $0.75 |
| Bedrock Titan Text Embeddings v2 (ingestion) | 1M tokens @ $0.02/M | $0.02 |
| S3 Vectors (KB vector store) | 100MB + ~500 queries | $0.01 |
| DynamoDB on-demand | ~500 reads + 200 writes | $0.001 |
| S3 (documents + static) | 100MB + ~500 PUT/GET | $0.01 |
| CloudFront (Asia tier) | 1GB outbound @ $0.085/GB | $0.09 |
| KMS CMK | 1 key × $1/month prorated 48h | $0.07 |
| VPC Interface Endpoint (Bedrock, Singapore) | $0.013/hr × 48h | $0.62 |
| **Total estimate (S3 Vectors path)** | | **~$1.57 — 1.6% of $100 cap** |
| **Alt: OpenSearch Serverless path** | 2 OCU × $0.288/hr × 48h replaces S3 Vectors | **~$29.20 — 29% of $100 cap** |

> Detailed line-by-line breakdown + worst-case scenarios: [`W7_cost_estimates.md`](./W7_cost_estimates.md).

---

### Reference B — FinTech: "BudgetBot" (one possible approach)

This example covers all 7 mandatory capabilities and demonstrates Advanced Cost Insights as the chosen optional capability. This is one possible approach — your team may pick different services and a different optional capability.

**Mandatory capabilities covered (#1-7):**
[#1 UI — static] CloudFront + S3 static site → [#1 UI — API entry] API Gateway REST API → [#2 Compute] Lambda Python 3.12 → [#3 AI/ML] Bedrock InvokeModel + chosen foundation model (Haiku is one option) JSON categorization → [#4 Data] RDS PostgreSQL db.t3.micro transaction records. [#5 Object Storage] S3 upload bucket. [#6 Network] VPC: Lambda in private subnet, RDS in private subnet, SG references Lambda SG not CIDR. [#7 Identity baseline] IAM Lambda execution role with specific DynamoDB and Bedrock actions only.

**Optional capability attempted: Advanced Cost Insights (#9)**
Three daily Cost Explorer screenshots (Day 1 EOD / Day 2 EOD / Friday morning), written observation per screenshot explaining spend trend, cost-per-feature analysis in Evidence Pack (Lambda cost per 1000 API calls vs Bedrock token cost per categorization batch), Cost Anomaly Detection alert demo.

Your team may choose differently — e.g., DynamoDB if your analysis queries are simpler key-value lookups, or ECS Fargate if your backend needs a long-running process for CSV parsing. What matters is that you can justify the trade-off.

**Key service decisions in this example:**

| Decision | Rationale |
|----------|-----------|
| RDS PostgreSQL over DynamoDB | Spending analysis requires SQL: `SELECT category, SUM(amount) FROM transactions WHERE user_id=? AND EXTRACT(MONTH FROM date)=? GROUP BY category`. DynamoDB cannot do multi-attribute aggregations without a Scan — too slow and expensive at scale. |
| Direct InvokeModel over KB | The AI task is one-shot classification of a transaction string, not retrieval from a document corpus. You construct the prompt ("categorize this transaction: ...") and send it. No retrieval step needed. |
| RDS Proxy | Lambda can spawn 50+ concurrent invocations during a burst. Each opens a DB connection. db.t3.micro max connections ≈ 85. RDS Proxy pools connections and multiplexes — prevents "FATAL: remaining connection slots are reserved" errors mid-demo. |
| Single-AZ RDS | Multi-AZ doubles database cost ($0.036/hr → $0.072/hr). For a 48-hour hackathon, the failover protection is not worth $1.73. Document this trade-off explicitly in the Evidence Pack. |

**Data flow:**
User uploads CSV bank statement → S3 PutObject trigger → Lambda parses CSV rows (pandas or csv module) → for each transaction row: call Bedrock InvokeModel with categorization prompt → receive JSON `{"category": "Food", "confidence": "high"}` → batch INSERT to RDS `transactions` table → DML completes → UI refreshes. On query: user asks "spending summary for May" → API Gateway GET `/summary?month=2026-05` → Lambda → `SELECT category, SUM(amount), COUNT(*) FROM transactions WHERE user_id=? AND date_trunc('month', date)=?::date GROUP BY category ORDER BY SUM(amount) DESC` → chart data to frontend.

**Sample Bedrock prompt:**
```
Categorize the following bank transaction into exactly one category.
Categories: Food, Transport, Shopping, Utilities, Entertainment, Health, Subscriptions, Income, Transfer, Other

Transaction: "{transaction_description}"
Amount: {amount}
Date: {date}

Respond with JSON only. No explanation.
{"category": "<category>", "confidence": "high|medium|low"}
```

**Estimated cost breakdown (48 hours, ap-southeast-1 Singapore list price):**

| Service | Calculation | Cost |
|---------|-------------|------|
| Lambda | 500 invocations × 512MB × 3s = 750 GB-sec | $0.012 |
| API Gateway REST | 500 requests @ $3.50/M | $0.002 |
| Bedrock Claude 3.5 Haiku (InvokeModel) | 2000 txns × 150 input + 30 output = 300K input + 60K output | $0.60 |
| RDS db.t3.micro PostgreSQL single-AZ (Singapore) | $0.026/hr × 48h | $1.25 |
| RDS gp3 storage | 20GB × $0.138/GB-month × (48/720) | $0.18 |
| RDS Proxy | $0.018/hr × 48h | $0.86 |
| S3 (statements + static) | 10MB + ~200 PUT/GET | $0.002 |
| CloudFront (Asia tier) | 500MB outbound | $0.04 |
| KMS CMK | 1 key prorated 48h | $0.07 |
| VPC Interface Endpoint (Bedrock, Singapore) | $0.013/hr × 48h | $0.62 |
| **Total estimate** | | **~$3.65 — 3.7% of $100 cap** |

> The biggest cost driver here is RDS (instance + proxy + storage = $2.29), not the AI. See [`W7_cost_estimates.md`](./W7_cost_estimates.md).

---

### Reference C — ProductivityTech: "DocHub" (one possible approach)

This example covers all 7 mandatory capabilities and demonstrates Advanced Security as the chosen optional capability. This is one possible approach — your team may pick different services and a different optional capability.

**Mandatory capabilities covered (#1-7):**
[#1 UI — static] CloudFront + S3 static site → [#1 UI — API entry] API Gateway → [#2 Compute] Lambda → [#3 AI/ML] Bedrock Agent with Lambda action group + Bedrock Knowledge Base + chosen vector store (S3 Vectors is one option) with `tenant_id` metadata filter → [#4 Data] DynamoDB document metadata PK=`tenant_id` SK=`doc_id`. [#5 Object Storage] S3 document bucket per-tenant prefixes. [#6 Network] VPC: Lambda in private subnet, DynamoDB via Gateway Endpoint, Bedrock via Interface Endpoint. [#7 Identity baseline] IAM Lambda execution role with least-privilege Bedrock + S3 + DynamoDB actions.

**Optional capability attempted: Advanced Security (#10)**
KMS Customer Managed Key applied to S3 document bucket + DynamoDB table encryption with CMK. Key rotation enabled. AWS Config rule deployed to check S3 Block Public Access is enabled. CloudTrail events confirm KMS GenerateDataKey calls on each document upload.

Your team may choose differently — e.g., RDS for document metadata if your query patterns need complex filtering, or Full Observability as your optional capability instead of Advanced Security. Scope discipline matters more than using the most complex service.

**Key service decisions in this example:**

| Decision | Rationale |
|----------|-----------|
| Bedrock Agent over pure KB retrieve | Agent enables tool use — the action group exposes a "list documents by type" Lambda tool. User can ask "show me only contracts" and the Agent decides to call the tool, then retrieve from the filtered result set. A pure KB retrieve call cannot dynamically filter before retrieval. |
| KB metadata filtering for tenant isolation | Every document is ingested with `metadata={"tenant_id": "tenant-123", "doc_type": "contract"}`. Every retrieve call includes `retrievalConfiguration.vectorSearchConfiguration.filter = {"equals": {"key": "tenant_id", "value": current_tenant_id}}`. Isolation is enforced at the vector search layer — a bug in application code cannot leak cross-tenant results because the retrieval itself is filtered. |
| DynamoDB for document metadata | Tenant document library is always queried as "all docs for tenant X, sorted by uploaded_at" — DynamoDB GSI with PK=`tenant_id`, SK=`uploaded_at` serves this with a single Query, no scan. |
| S3 Vectors over OpenSearch Serverless | OpenSearch Serverless minimum: 2 OCU × $0.24/hr = $5.76/day = $11.52 over 48 hours. S3 Vectors has no minimum OCU charge. For a $100 cap, OpenSearch Serverless is still feasible but consumes a large share of the budget on infrastructure alone — plan accordingly. |

**Data flow:**
User logs in → Cognito issues JWT with `custom:tenant_id=tenant-123` → user uploads contract PDF → API Gateway POST `/upload` with JWT → Lambda extracts `tenant_id` from JWT (`cognito:custom:tenant_id`) → S3 PutObject to `tenant-123/docs/{doc_id}.pdf` → Bedrock KB StartIngestionJob with metadata `{"tenant_id": "tenant-123", "doc_type": "contract"}` → DynamoDB PutItem for document metadata → On query: user asks "what are the penalty clauses?" → Lambda → Bedrock Agent InvokeAgent with session context and tenant_id → Agent decides: call KB retrieve filtered by `tenant_id=tenant-123` → retrieve top-K chunks → Claude Haiku generates answer with source citations → response to UI with document name + page reference.

**Sample Bedrock prompt (Agent system prompt):**
```
You are a document intelligence assistant for a multi-tenant SaaS platform.
You only have access to documents belonging to the current user's organization.
NEVER reference documents from other organizations.
When answering, always cite the document name and the relevant section.
If you cannot find the answer in the available documents, say:
"I could not find this information in your organization's documents."
Use the list_documents tool to find available documents by type before answering
questions that reference specific document categories.
```

**Estimated cost breakdown (48 hours, ap-southeast-1 Singapore list price):**

| Service | Calculation | Cost |
|---------|-------------|------|
| Lambda (main + action group) | 300 invocations × 1024MB × 5s = 1,500 GB-sec | $0.025 |
| API Gateway HTTP | 300 requests | $0.0003 |
| Bedrock Claude 3.5 Haiku (Agent + KB) | 50 queries × 3K retrieve + 500 generate = 150K input + 25K output | $0.28 |
| Bedrock Titan Text Embeddings v2 (ingestion of 20 docs) | 2M tokens @ $0.02/M | $0.04 |
| S3 Vectors (KB vector store) | 200MB + ~50 queries | $0.01 |
| DynamoDB on-demand | ~300 reads + 100 writes | $0.0003 |
| S3 (documents + static) | 200MB + ~400 PUT/GET | $0.01 |
| CloudFront (Asia tier) | 1GB outbound | $0.09 |
| KMS CMK | 1 key prorated 48h | $0.07 |
| Cognito User Pool | <100 MAU (free tier up to 50K) | FREE |
| VPC Interface Endpoints × 2 (Bedrock + Secrets Manager, Singapore) | 2 × $0.013/hr × 48h | $1.25 |
| **Total estimate (S3 Vectors path)** | | **~$1.77 — 1.8% of $100 cap** |
| **Alt: OpenSearch Serverless path** | 2 OCU × $0.288/hr × 48h (Singapore) | **~$29.40 — 29% of $100 cap** |

> **Warning — OpenSearch Serverless cost:** Check S3 Vectors availability in `ap-southeast-1` before locking the design. If S3 Vectors is not available in your selected region, OpenSearch Serverless adds ~$27.65 (2 OCU × $0.288/hr × 48h in Singapore; ~$23.04 in us-east-1). With the $100 cap that is still comfortable (~29% of budget), but it is your single largest fixed cost — leave it at default minimum OCU, do not over-provision, and delete the collection immediately after Friday demo. Detailed breakdown in [`W7_cost_estimates.md`](./W7_cost_estimates.md).

---

## Evidence Pack — `docs/W7_evidence.md`

This file lives in your GitHub repo. It is the graded artifact for Criterion IV. Build it during the build — a screenshot at 14:00 Wednesday is always more credible than one reconstructed Thursday night.

**Required sections:**

| Section | Contents |
|---------|----------|
| **1. Cover** | Group number, member names, live URL, repo link, domain choice, total spend |
| **2. Pitch and Vision** | Use case (2-3 sentences), target user, why this domain matters |
| **3. Architecture** | Final diagram (reflects what is deployed), service decisions table, 2-3 conscious trade-offs |
| **4. Cost Discipline** | 3 cost screenshots (Day 1 EOD / Day 2 EOD / Friday pre-demo), breakdown by service, written observation |
| **5. Security** | IAM roles + compute execution role scope (required) + the security area from your Optional #10 choice (encryption / audit / secrets / network) with concrete evidence: policy screenshot, log event, rotation status, alarm trigger, or VPC Flow Log sample. **No specific service mandated — pick what fits.** |
| **6. Monitoring** | CloudWatch dashboard screenshot, alarm config, Log Insights query with real results |
| **6.5 Measurement & Decisions** ★ | **NEW — required.** At least 2 architectural decisions using the structured template below. Boilerplate / vague text will be flagged as "đối phó" by trainer + by Claude during pre-review. See full spec below the table. |
| **7. Lessons Learned** | 200 words: what went well, what you'd do differently, what surprised you. Should reference real-world parallel and one concrete failure case. |
| **8. Teardown Plan** | Ordered list of resources to delete + CLI commands or CFN delete command |

---

### Section 6.5 — Measurement & Decisions (Required, anti-đối phó)

This section exists because of a real lesson from W6: groups built features just to check rubric boxes, not because they thought about real users or measured what worked. W7 fixes that by requiring **structured proof** of at least 2 architectural decisions.

**Required template — one block per decision (minimum 2 decisions):**

```
DECISION: [What you chose — be specific. "Bedrock Haiku" is too vague.
           "Bedrock Haiku for transaction classification because cost < accuracy threshold" is better.]

ALTERNATIVES CONSIDERED:
- [Option A] — eliminated because: [concrete reason with a number or observation]
- [Option B] — eliminated because: [concrete reason]
(at least 2 alternatives — single-option "decisions" are not decisions)

MEASUREMENT:
- [Metric 1] = [number with unit] — [how you measured]
- [Metric 2] = [number with unit] — [how you measured]
(at least 1 measurement with a real number)

EVIDENCE:
- [Screenshot path / Cost Explorer link / CloudWatch metric / spreadsheet / log query]
(at least 1 piece of evidence — claims without proof score 0 for that decision)

TRADE-OFF ACCEPTED:
- [What you gave up by choosing this path — be specific]
```

**✓ Acceptable example (passes the gate):**

```
DECISION: Use pypdf for text-extractable PDFs, fall back to Textract only when text density
          per page < 100 characters.

ALTERNATIVES CONSIDERED:
- Textract everywhere — eliminated: Textract costs $0.0015/page × 200 pages/day = $0.30/day
  excess vs pypdf $0; we measured 73% of our 30 test PDFs were text-extractable.
- Bedrock Vision (Claude reads page images) — eliminated: 2.3s/page latency vs pypdf 0.05s;
  cost ~$0.04/page vs $0; only justified for figure-heavy decks.

MEASUREMENT:
- pypdf success rate on our 30 sample PDFs = 73% (22/30 had clean text extraction)
- Cost saved per 1000 uploads = $0.80 vs Textract-everywhere
- Hybrid latency: p50 = 0.4s, p99 = 2.1s

EVIDENCE:
- `docs/evidence/pdf_extraction_benchmark.xlsx` — 30 sample PDFs scored
- CloudWatch screenshot of Lambda duration histogram (`docs/evidence/lambda_duration.png`)

TRADE-OFF ACCEPTED:
- pypdf cannot read tables-as-images. 8% of uploads hit this path and re-process via
  Textract on demand. Lambda fallback duration p99 spikes to 2.1s when this fires.
```

**✗ Anti-pattern (will be flagged as đối phó — score 0 for this block):**

```
DECISION: We use Bedrock Haiku.
ALTERNATIVES: We considered Sonnet but Haiku is cheaper.
MEASUREMENT: It works.
EVIDENCE: See repo.
TRADE-OFF: None.
```

**Why anti-đối phó signals are graded:**

The Evidence Pack is YOUR proof that you thought about the problem, not just shipped to a deadline. Trainers and Claude will compare each block against the anti-pattern above. Specific signals that earn credit:

1. **Decision provenance** — not "we chose X" but "we considered A/B/C, eliminated B because [Y measurement], eliminated C because [Z constraint], chose A"
2. **Concrete numbers** — `$0.04/page`, `73%`, `2.1s p99`, `30 sample PDFs`, NOT "cheap", "fast", "good enough"
3. **Evidence link** — a path to a real artifact in your repo or AWS console screenshot
4. **Trade-off awareness** — what you gave up. If you can't name a trade-off, you didn't really make a decision
5. **Failure stories** — what you tried and abandoned. The 8% pypdf-can't-read path in the example is a failure story.

**Volume vs depth:** 2 strong blocks beats 6 weak ones. If you write 2 decisions that match the acceptable example above, that's a strong submission. Don't dilute by listing every minor choice.

**Anti-cheap-shot rule (links to cost gate):** to qualify for the **under-$30 cost bonus (Path H)**, your §6.5 must document what you cut to stay lean. "We're at $5 because we deployed almost nothing" is under-deployment, not discipline.

---

## Friday Presentation Format

40 minutes per group, spread across Fri–Sat. Practice the timing before Demo Day. **Architecture Walkthrough is the largest block (14 min) — invest in slides and rehearsal.**

| Part | Time | Content |
|------|------|---------|
| **1. Pitch + Vision** | 5 min | Domain story, target user, why this use case matters |
| **2. Live Demo** | 7 min | Trainer's browser → URL → login → upload → AI result visible end to end + persistence check |
| **3. Architecture Walkthrough** ★ | 14 min | DEEP-DIVE: diagram + 7 mandatory + 1 optional capability + 9 service decisions (compute / DB / vector / frontend / IaC / VPC / identity / observability / cost) + 2-3 real trade-offs |
| **4. Individual QnA** | 12 min | Trainer picks 2-3 students at random — deep probes after the walkthrough |
| **5. Cost and Lessons Learned** | 2 min | Real Cost Explorer screenshot + top 3 drivers + "what we'd change" |

Before your slot: post your `docs/W7_evidence.md` commit link in the trainer channel. No link = Criterion IV pre-flagged before you start.

---

## Bonus Paths (cap +0.5 total)

One bonus done well beats three done halfway.

| Path | What | Difficulty | How to prove |
|------|------|------------|-------------|
| **A. Multi-region failover** | Route 53 health check + secondary stack in second region | Hard | Live failover demo or video + CloudWatch health check state change |
| **B. CI/CD pipeline** | CodePipeline or GitHub Actions auto-deploys on push to main | Medium | Push a change during demo, show pipeline run and live update |
| **C. Custom domain + HTTPS** | Route 53 hosted zone + ACM cert on CloudFront | Easy | Custom URL in trainer's browser, ACM cert status: Issued |
| **D. Real users (5+)** | Five external people used the app before Friday with documented feedback | Easy | User session screenshots + written feedback in Evidence Pack |
| **E. IaC full coverage** | Full infra in your chosen IaC — CloudFormation / CDK / Terraform / SAM / Pulumi / AWS Cloud Control API. Can teardown + redeploy in 5 minutes. | Medium | Live deploy command during demo |
| **F. AI safety mechanism** | Content filter / PII redaction / prompt injection guard via Bedrock Guardrails OR Comprehend PII detection OR LLM-as-judge pre-filter OR custom prompt-engineering defense | Medium | Show input → blocked/sanitized response with reasoning |
| **G. Cost optimization** | Real before/after measurement with dollar amounts | Medium | Side-by-side screenshots with calculation in Evidence Pack |
| **H. Cost discipline under $30 + quality** | Total spend under $30 + clean teardown + Criterion II ≥ 4.0 + Criterion III ≥ 4.0 + Section 6.5 documents what was cut to stay lean | Medium | Cost Explorer screenshot Mon 2/6 + evidence of conscious trade-offs (not just under-deployment) |

---

## What "Done" Looks Like

By the time your group finishes on Friday, a trainer should be able to verify all 7 mandatory capabilities in sequence, then check whether any optional capability was attempted:

1. Open your URL — loads in their browser, no SSL errors, under 5 seconds (mandatory #1 User Interface)
2. Upload a sample file — the one in your repo under `docs/sample_input/`
3. See the AI process it — result visible in the UI within 30 seconds (mandatory #3 AI/ML Feature)
4. Confirm state persists — previously uploaded file accessible in a fresh session (mandatory #4 Data Persistence)
5. Check network isolation — DB is in a private subnet with SG scoped to compute layer only (mandatory #6 Network Foundation)
6. Open your Evidence Pack — all 8 sections present, screenshots timestamped during build, IAM roles documented (mandatory #7 Identity and Access baseline)
7. Check the cost — Cost Explorer filtered by `Team=G<N>` shows under $100, three daily screenshots present
8. Ask which optional capability was attempted — bonus credit if it is present and working, partial credit if partial progress shown

---

## Critical Pitfalls — Read These Before You Start

**1. Bedrock model access not enabled**
You call InvokeModel and get `AccessDeniedException: You don't have access to the model with the specified model ID`. Fix: AWS Console → Amazon Bedrock → Model access → Request access for WHICHEVER foundation model(s) your team picked (Claude / Llama / Mistral / Titan / Cohere / etc.) + an embeddings model if RAG-based. Do this Wednesday morning before writing any code.

**2. NAT Gateway running 24/7**
NAT Gateway charges $0.045/hour — $2.16 over 48 hours, before a single user hits your app. If Lambda only calls AWS services (Bedrock, S3, DynamoDB), use VPC endpoints instead. S3 and DynamoDB use free Gateway endpoints. Bedrock and Secrets Manager use Interface endpoints (~$0.01/hr each).

**3. AWS keys committed to public GitHub**
Bots scan public repos for AWS keys within minutes of a push. Fix: use IAM execution roles for Lambda, instance profiles for EC2, Parameter Store for secrets. Add `.env` to `.gitignore` before your first commit. Never put `AWS_ACCESS_KEY_ID` in code.

**4. Demo URL is HTTP, not HTTPS**
Modern browsers block certain features on HTTP. CloudFront gives you HTTPS on the default `*.cloudfront.net` domain at no extra cost. Plan this on Day 1.

**5. Single point of failure on console access**
One person holds all the credentials. That person gets sick Thursday night. Fix: create IAM users for every team member on Wednesday morning. Share test credentials in the group chat.

**6. Forgetting teardown means continued billing**
Your account does not reset. An RDS instance left running costs $13/month. An OpenSearch Serverless collection costs $175/month. Delete everything by Sunday 1/6 EOD. Commit the teardown confirmation to your repo.

**7. Using Claude Sonnet during development**
Foundation model price spread is huge: Sonnet ~12x Haiku, Mistral Large ~16x Llama. Multiple debugging sessions with an expensive model can easily consume $10-20 of your $100 cap before you notice. **Always benchmark the cheapest reasonable model first** on YOUR task (5-10 sample queries, eyeball quality). Upgrade only if measurement justifies.

**8. Free tier misconceptions**
Bedrock is NOT free tier. NAT Gateway is NOT free tier. KMS CMK charges $1/month (prorated). Know what you will pay before you provision it.

**9. Trying to hit all optional capabilities = burnout**
Focus on 7 mandatory rock-solid first. Pick ONE optional capability to do well — it drives your Likert scores higher than three half-done optionals. 1 done well > 3 half-done. Same principle applies to bonus paths: pick one and prove it, not three and guess them. The time budget is clear: 12-14 hours to get 7 mandatory solid, 2-3 hours for one optional, 1-2 hours for one bonus path. You have 16 hours total across two days.

**10. Over-engineering the UI: 4 hours on React when a plain HTML form works in 30 minutes**
Your UI does not need to be beautiful. A single HTML page with a file input, a submit button, and a text area for the AI response is enough. Spending Wednesday afternoon building a polished React frontend while your backend is undeployed is the fastest path to a failed Friday demo.

**11. Setting up full Cognito signup/login/password reset**
Cognito is OPTIONAL under capability #7. A hardcoded test user, IAM-based access, or signed URLs are all legitimate choices. If you spend 3 hours building a complete Cognito auth flow with email verification, account recovery, and custom UI — that is time you did not spend on your AI feature, which is graded.

**12. Refactoring code mid-hackathon**
"We should restructure this Lambda into three separate functions with a shared layer" is a sentence that should never be spoken between Wednesday morning and Friday 09:00. Ship the working single-file Lambda. Refactor after the demo if it bothers you. The trainer does not read your code — they interact with your URL.

---

## Why This Week Matters

A portfolio entry that says "I deployed a static website to S3" is one line on a resume. A portfolio entry that says "I built and shipped a production-ready AI SaaS platform — user auth, Bedrock AI pipeline, serverless API, VPC-isolated database, live HTTPS URL, CloudWatch monitoring, under $100 — in 48 hours on a real cloud account" is a story you tell in every interview. It shows architecture thinking, cost discipline, operational awareness, and the ability to ship under pressure.

W7 is designed to create that story. The skills from six weeks exist for this moment. Use them.

By Friday, you will have a live URL, a GitHub repo, and a system that works. Keep the repo public after teardown. You earned it.

Good luck. Ship it.
