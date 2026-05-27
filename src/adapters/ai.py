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

    def _build_rag_model_arn(self) -> str:
        """Build model ARN for RetrieveAndGenerate.

        Newer models (Claude 3.5 Sonnet v2+, Claude Sonnet 4+) do NOT support
        on-demand throughput directly. They require a cross-region inference
        profile, whose ID is prefixed with the region group (us./eu./ap.).

        Examples:
          Old (on-demand OK):  arn:..::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0
          New (needs profile): arn:..::foundation-model/ap.anthropic.claude-sonnet-4-5-20250929-v1:0
        """
        model_id = self.model_id
        region_group = self.region.split("-")[0]  # "us", "eu", "ap"

        # Models released after mid-2024 require cross-region inference profiles.
        # If the model_id doesn't already carry a region-group prefix, add one.
        NEEDS_PROFILE_PREFIXES = (
            "claude-3-5-sonnet-20241022",
            "claude-3-7",
            "claude-sonnet-4",
            "claude-3-5-haiku-20250307",  # haiku v2+
        )
        needs_prefix = any(p in model_id for p in NEEDS_PROFILE_PREFIXES)
        already_prefixed = any(model_id.startswith(f"{p}.") for p in ("us", "eu", "ap"))

        if needs_prefix and not already_prefixed:
            model_id = f"{region_group}.{model_id}"

        return f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"

    def retrieve_and_generate(self, query: str, kb_id: str = "") -> dict:
        if not kb_id:
            raise ValueError("VECTOR_BEDROCK_KB_ID must be set for Bedrock KB retrieve_and_generate")

        model_arn = self._build_rag_model_arn()
        try:
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
        except Exception as first_err:
            # Fallback: if the configured model fails (e.g. on-demand not supported),
            # retry once with haiku which always supports on-demand throughput.
            import logging
            logging.getLogger("StudyBot").warning(
                f"retrieve_and_generate failed with model {model_arn}: {first_err}. "
                "Retrying with claude-3-5-haiku fallback."
            )
            fallback_arn = (
                f"arn:aws:bedrock:{self.region}::foundation-model/"
                f"anthropic.claude-3-5-haiku-20241022-v1:0"
            )
            resp = self.agent_runtime.retrieve_and_generate(
                input={"text": query},
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": kb_id,
                        "modelArn": fallback_arn,
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
