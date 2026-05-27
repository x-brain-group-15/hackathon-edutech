"""AI adapters. Pick via AI_BACKEND env var.

Interface:
    invoke(prompt, **kwargs) -> str
    retrieve_and_generate(query, kb_id="") -> dict with {"answer": str, "citations": list}
"""
from typing import Any


class BedrockAI:
    """Real Amazon Bedrock client. Uses Converse API for invoke; bedrock-agent-runtime for RAG."""

    def __init__(self, region: str, model_id: str):
        import boto3
        self.region = region
        self.model_id = model_id
        self.runtime = boto3.client("bedrock-runtime", region_name=region)
        self.agent_runtime = boto3.client("bedrock-agent-runtime", region_name=region)

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        max_tokens = kwargs.get("max_tokens", 1024)
        resp = self.runtime.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": kwargs.get("temperature", 0.2)},
        )
        return resp["output"]["message"]["content"][0]["text"]

    def retrieve_and_generate(self, query: str, kb_id: str = "") -> dict:
        if not kb_id:
            raise ValueError("VECTOR_BEDROCK_KB_ID must be set for Bedrock KB retrieve_and_generate")
        model_arn = f"arn:aws:bedrock:{self.region}::foundation-model/{self.model_id}"
        resp = self.agent_runtime.retrieve_and_generate(
            input={"text": query},
            retrieveAndGenerateConfiguration={
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": kb_id,
                    "modelArn": model_arn,
                },
            },
        )
        return {
            "answer": resp["output"]["text"],
            "citations": [
                {
                    "text": ref.get("content", {}).get("text", ""),
                    "source": ref.get("location", {}),
                }
                for citation in resp.get("citations", [])
                for ref in citation.get("retrievedReferences", [])
            ],
        }


class LocalAI:
    """Local stub. Returns canned responses. Use for development without AWS credentials."""

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        snippet = prompt[:200].replace("\n", " ")
        return (
            f"[LOCAL_AI_STUB] Received prompt: {snippet!r}... "
            "Set AI_BACKEND=bedrock + AWS credentials for real Bedrock output."
        )

    def retrieve_and_generate(self, query: str, kb_id: str = "") -> dict:
        return {
            "answer": (
                f"[LOCAL_AI_STUB] Query received: {query!r}. "
                "Set AI_BACKEND=bedrock and VECTOR_BACKEND=bedrock_kb for real RAG."
            ),
            "citations": [],
        }
