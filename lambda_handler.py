"""AWS Lambda entry point — wraps the FastAPI app with Mangum.

Usage:
    Lambda handler: studybot.lambda_handler.handler

This file is the ONLY addition needed to run the existing FastAPI app on Lambda.
The rest of the codebase (src/app.py, adapters, handlers) is unchanged.

Deploy steps:
    1. pip install -r requirements-lambda.txt -t ./package/
    2. cp -r src frontend package/
    3. cp lambda_handler.py .env package/
    4. cd package && zip -r ../studybot.zip .
    5. aws lambda update-function-code --function-name studybot-api --zip-file fileb://../studybot.zip

Or use SAM: sam build && sam deploy  (see template.yaml)
"""
from mangum import Mangum
from src.app import app

# Mangum adapts ASGI (FastAPI) → AWS Lambda + API Gateway HTTP API event format.
# lifespan="off" disables FastAPI startup/shutdown events — not needed in Lambda
# (singletons are initialized at module-level in app.py, which is fine for Lambda).
handler = Mangum(app, lifespan="off")
