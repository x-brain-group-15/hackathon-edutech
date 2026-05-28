"""AI adapters. Pick via AI_BACKEND env var.

Interface:
    invoke(prompt, **kwargs) -> str
    retrieve_and_generate(query, kb_id="") -> dict with {"answer": str, "citations": list}
    generate_quiz_from_kb(prompt, **kwargs) -> str
"""
from typing import Any


class BedrockAI:
    """Real Amazon Bedrock client. Uses Converse API for invoke; bedrock-agent-runtime for RAG with fallbacks."""

    def __init__(self, region: str, model_id: str):
        import boto3
        self.region = region
        self.model_id = model_id
        self.runtime = boto3.client("bedrock-runtime", region_name=region)
        self.agent_runtime = boto3.client("bedrock-agent-runtime", region_name=region)

    def _build_arn_for_model(self, model_id: str) -> str:
        """Build model ARN or Inference Profile ARN dynamically based on region constraints."""
        if model_id.startswith("arn:aws:bedrock:"):
            return model_id

        region_group = self.region.split("-")[0]  # "us", "eu", "ap"

        # Models released after mid-2024 require cross-region inference profiles.
        NEEDS_PROFILE_PREFIXES = (
            "claude-3-5-sonnet",
            "claude-3-7",
            "claude-sonnet-4",
            "claude-3-5-haiku",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-sonnet-4-6",
            "nova-2-lite",
            "nova-lite",
            "nova-pro",
        )
        needs_prefix = any(p in model_id for p in NEEDS_PROFILE_PREFIXES)
        
        PROFILE_PREFIXES = ("us", "eu", "ap", "apac", "usac", "euac")
        already_prefixed = any(model_id.startswith(f"{p}.") for p in PROFILE_PREFIXES)

        if needs_prefix and not already_prefixed:
            model_id = f"{region_group}.{model_id}"

        # If it is a cross-region inference profile (prefixed with us., eu., ap., apac., etc.),
        # use the ::inference-profile/ ARN format instead of ::foundation-model/
        is_profile = any(model_id.startswith(f"{p}.") for p in PROFILE_PREFIXES)
        if is_profile:
            return f"arn:aws:bedrock:{self.region}::inference-profile/{model_id}"
        else:
            return f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        max_tokens = kwargs.get("max_tokens", 1024)
        
        # Fallback list in user-specified priority order
        models_to_try = [
            self.model_id,
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "amazon.nova-2-lite-v1:0",
            "amazon.nova-lite-v1:0",
            "anthropic.claude-haiku-4-5-20251001-v1:0",
            "anthropic.claude-sonnet-4-6",
            "amazon.nova-pro-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0"
        ]

        import logging
        logger = logging.getLogger("StudyBot")

        last_error = None
        for model_id in models_to_try:
            model_arn = self._build_arn_for_model(model_id)
            logger.info(f"Attempting invoke with model: {model_id} (ARN: {model_arn})")
            try:
                resp = self.runtime.converse(
                    modelId=model_arn,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    inferenceConfig={"maxTokens": max_tokens, "temperature": kwargs.get("temperature", 0.2)},
                )
                logger.info(f"Successfully invoked Converse API using model: {model_id}")
                return resp["output"]["message"]["content"][0]["text"]
            except Exception as e:
                logger.warning(f"invoke failed with model {model_id}: {e}")
                last_error = e

        raise last_error

    def generate_quiz_from_kb(self, prompt: str, **kwargs: Any) -> str:
        """Generate quiz JSON through Bedrock Converse API."""
        return self.invoke(
            prompt,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.1),
        )

    def retrieve_and_generate(self, query: str, kb_id: str = "") -> dict:
        if not kb_id:
            raise ValueError("VECTOR_BEDROCK_KB_ID must be set for Bedrock KB retrieve_and_generate")

        # Fallback list in user-specified priority order
        models_to_try = [
            self.model_id,
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "amazon.nova-2-lite-v1:0",
            "amazon.nova-lite-v1:0",
            "anthropic.claude-haiku-4-5-20251001-v1:0",
            "anthropic.claude-sonnet-4-6",
            "amazon.nova-pro-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0"
        ]

        import logging
        logger = logging.getLogger("StudyBot")

        last_error = None
        for model_id in models_to_try:
            model_arn = self._build_arn_for_model(model_id)
            logger.info(f"Attempting retrieve_and_generate with model: {model_id} (ARN: {model_arn})")
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
                logger.info(f"Successfully generated answer using model: {model_id}")
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
            except Exception as e:
                logger.warning(f"retrieve_and_generate failed with model {model_id}: {e}")
                last_error = e

        raise last_error



class LocalAI:
    """Local stub. Returns canned responses. Use for development without AWS credentials."""

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        prompt_lower = prompt.lower()
        if "practice quiz generator" in prompt_lower:
            return """
            [
              {
                "id": "local-q1",
                "question": "Where does photosynthesis occur?",
                "options": ["In chloroplasts", "In ribosomes", "In mitochondria", "In the nucleus"],
                "correct_answer": "In chloroplasts",
                "explanation": "The provided notes identify chloroplasts as the site of photosynthesis."
              },
              {
                "id": "local-q2",
                "question": "What do light reactions split during photosynthesis?",
                "options": ["Water", "Glucose", "Carbon dioxide", "Chlorophyll"],
                "correct_answer": "Water",
                "explanation": "The notes state that light reactions split water and release oxygen."
              }
            ]
            """
        if "cornell note-taking format" in prompt_lower:
            return """
            {
              "cues": [
                {"keyword": "Photosynthesis", "association": "Chloroplasts"},
                {"keyword": "Light Reactions", "association": "Thylakoid Membrane"},
                {"keyword": "Calvin Cycle", "association": "Stroma"},
                {"keyword": "Chlorophyll", "association": "Pigment"},
                {"keyword": "ATP", "association": "Energy carrier"}
              ],
              "notes": [
                "Photosynthesis converts light energy into chemical energy.",
                "Light reactions split water molecules, releasing oxygen as a byproduct.",
                "ATP and NADPH are synthesized to power the Calvin Cycle.",
                "Carbon dioxide fixation occurs in the stroma during the light-independent phase.",
                "Chloroplasts contain chlorophyll pigments that absorb light wavelengths."
              ],
              "summary": "Photosynthesis is the primary process by which plants synthesize organic compounds from CO2 and water, utilizing sunlight as an energy source."
            }
            """
        elif "mermaid.js" in prompt_lower or "mindmap" in prompt_lower:
            return """
            mindmap
              root((Photosynthesis))
                Light Reactions
                  Water
                  Oxygen
                Calvin Cycle
                  CO2
                  Sugar
            """
        elif "flashcards" in prompt_lower:
            return """
            [
              {"front": "Where does photosynthesis occur?", "back": "In the chloroplasts of plant cells."},
              {"front": "What does light-dependent phase produce?", "back": "Oxygen, ATP, and NADPH."}
            ]
            """
        
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

    def generate_quiz_from_kb(self, prompt: str, **kwargs: Any) -> str:
        return self.invoke(prompt, **kwargs)
