.PHONY: install run test clean lambda-build lambda-test sam-deploy sam-delete

# ---- Local development ----
install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@echo ""
	@echo "Done. Next:  source .venv/bin/activate && cp .env.example .env && make run"

run:
	uvicorn src.app:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v tests/

clean:
	rm -rf _data __pycache__ .pytest_cache src/__pycache__ src/adapters/__pycache__ tests/__pycache__ package studybot.zip .aws-sam

# ---- Lambda packaging (manual zip — no SAM required) ----
# Installs dependencies into ./package/, copies source, zips everything.
lambda-build:
	@echo "--- Building Lambda deployment package ---"
	rm -rf package && mkdir package
	pip install -r requirements-lambda.txt -t ./package/ --quiet
	cp -r src frontend lambda_handler.py package/
	@echo "Copying .env (ensure AI_BACKEND=bedrock before zipping)"
	@test -f .env && cp .env package/ || echo "No .env found — Lambda will use env vars from SAM/Console"
	cd package && zip -r ../studybot.zip . -x "*.pyc" -x "*/__pycache__/*" -q
	@echo ""
	@echo "Done: studybot.zip ($(shell du -sh studybot.zip | cut -f1))"
	@echo "Deploy: aws lambda update-function-code --function-name studybot-api-<team> --zip-file fileb://studybot.zip"

# Quick smoke test of the Lambda handler locally (requires mangum installed)
lambda-test:
	@echo "--- Testing lambda_handler import ---"
	python -c "from lambda_handler import handler; print('OK — handler:', handler)"

# ---- SAM (recommended — handles build + deploy + rollback) ----
# Prerequisites: pip install aws-sam-cli  OR  brew install aws-sam-cli
sam-build:
	sam build --use-container

sam-deploy:
	@echo "--- Deploying with SAM (guided first time) ---"
	sam deploy --guided

# Teardown: deletes Lambda, API Gateway, DynamoDB, CloudWatch resources
sam-delete:
	@echo "--- Tearing down all SAM-managed resources ---"
	sam delete --no-prompts
	@echo "Remember: manually empty + delete S3 buckets and Bedrock KB (not in SAM stack)"
