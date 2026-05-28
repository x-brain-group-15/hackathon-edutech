"""Vector store adapters. Pick via VECTOR_BACKEND env var.

Interface:
    ingest(doc_id, text, metadata=None) -> None
    search(query, top_k=5, filter=None) -> list[dict] (each has 'text', 'doc_id', 'score', 'metadata')
"""
import re
from collections import Counter
from typing import Optional


class BedrockKBVector:
    """Production: Bedrock Knowledge Base abstracts the vector store backend.

    Group still chooses the underlying vector store (OpenSearch Serverless, S3 Vectors,
    Aurora pgvector, Pinecone) when creating the KB in AWS console — that choice
    is invisible to this code.

    NOTE: KB ingestion is async via StartIngestionJob, normally triggered by S3 events.
    For simplicity, this adapter is search-only — ingestion happens through the
    Bedrock console or S3 → KB sync pipeline you set up separately.
    """

    def __init__(self, kb_id: str, region: str):
        import boto3
        from botocore.config import Config
        if not kb_id:
            raise ValueError("VECTOR_BEDROCK_KB_ID must be set for Bedrock KB backend")
        self.kb_id = kb_id
        # Use short connect (2.0s) and read (4.0s) timeouts to avoid hanging Lambda
        config_boto = Config(
            connect_timeout=2.0,
            read_timeout=4.0,
            retries={"max_attempts": 1}
        )
        self.agent_runtime = boto3.client("bedrock-agent-runtime", region_name=region, config=config_boto)

    def ingest(self, doc_id: str, text: str, metadata: Optional[dict] = None, **kwargs) -> None:
        # Ingestion is typically S3-event driven. Trigger a manual sync if needed
        # via StartIngestionJob — but the doc must already be in the KB's S3 source.
        # This adapter assumes upstream code uploaded to S3 already.
        try:
            import boto3
            import logging
            from botocore.config import Config
            logger = logging.getLogger("StudyBot")
            
            # Use a fast timeout (2.0s) so the Lambda doesn't hang if the bedrock-agent control plane endpoint
            # is unreachable from the isolated private subnet VPC (since there is no VPC endpoint for bedrock-agent)
            config = Config(connect_timeout=2.0, read_timeout=2.0, retries={"max_attempts": 0})
            client = boto3.client("bedrock-agent", region_name=self.agent_runtime.meta.region_name, config=config)
            ds_resp = client.list_data_sources(knowledgeBaseId=self.kb_id)
            ds_summaries = ds_resp.get("dataSourceSummaries", [])
            if ds_summaries:
                ds_id = ds_summaries[0]["dataSourceId"]
                client.start_ingestion_job(
                    knowledgeBaseId=self.kb_id,
                    dataSourceId=ds_id
                )
                logger.info(f"Triggered automatic Bedrock KB ingestion sync job for data source: {ds_id}")
        except Exception as e:
            import logging
            logging.getLogger("StudyBot").warning(f"Failed to auto-sync Bedrock KB data source (normal if IAM permissions not granted or network isolated): {str(e)}")

    def search(self, query: str, top_k: int = 5, filter: Optional[dict] = None) -> list:
        kwargs = {
            "knowledgeBaseId": self.kb_id,
            "retrievalQuery": {"text": query},
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {"numberOfResults": top_k}
            },
        }
        if filter:
            filter_list = [{"equals": {"key": k, "value": v}} for k, v in filter.items()]
            if len(filter_list) == 1:
                kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"] = filter_list[0]
            elif len(filter_list) > 1:
                kwargs["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"] = {
                    "andAll": filter_list
                }
        resp = self.agent_runtime.retrieve(**kwargs)
        return [
            {
                "text": r.get("content", {}).get("text", ""),
                "doc_id": r.get("metadata", {}).get("doc_id", ""),
                "score": r.get("score", 0.0),
                "metadata": r.get("metadata", {}),
            }
            for r in resp.get("retrievalResults", [])
        ]


class LocalVector:
    """Simple in-memory inverted index + TF scoring. NOT semantic — keyword only.

    Good enough for verifying the API contract locally. Production needs real
    embeddings + ANN — that's what Bedrock KB provides.
    """

    def __init__(self):
        self.docs: list[tuple[str, str, dict]] = []   # (doc_id, text, metadata)

    @staticmethod
    def _tokens(text: str) -> list:
        return [t.lower() for t in re.findall(r"\w+", text) if len(t) > 2]

    @staticmethod
    def _chunk(
        text: str,
        strategy: Optional[str] = None,
        size: Optional[int] = None,
        overlap: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> list:
        from src import chunker
        from src.config import config

        strat = strategy or config.chunking_strategy
        sz = size or config.chunk_size
        ov = overlap or config.chunk_overlap
        th = threshold or config.semantic_threshold

        if strat == "structural":
            return chunker.chunk_structural(text)
        elif strat == "semantic":
            return chunker.chunk_semantic(text, threshold=th)
        else:  # fixed_size
            return chunker.chunk_fixed(text, size=sz, overlap=ov)

    def clear_doc(self, doc_id: str) -> None:
        self.docs = [d for d in self.docs if d[2].get("doc_id") != doc_id]

    def ingest(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[dict] = None,
        strategy: Optional[str] = None,
        size: Optional[int] = None,
        overlap: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> None:
        md = metadata or {}
        chunks = self._chunk(
            text,
            strategy=strategy,
            size=size,
            overlap=overlap,
            threshold=threshold,
        )
        for i, chunk in enumerate(chunks):
            self.docs.append((f"{doc_id}#{i}", chunk, {**md, "doc_id": doc_id, "chunk_idx": i}))

    def _seed_default_document(self, user_id: str) -> None:
        default_text = (
            "Photosynthesis is the process used by plants, algae and certain bacteria to convert light energy into chemical energy. "
            "Photosynthesis occurs in chloroplasts, which contain chlorophyll pigments that absorb light wavelengths. "
            "The light-dependent phase occurs in the thylakoid membrane where light reactions split water molecules, releasing oxygen as a byproduct. "
            "ATP and NADPH are synthesized to power the Calvin Cycle. "
            "The light-independent phase, also known as the Calvin Cycle, occurs in the stroma where carbon dioxide fixation takes place. "
            "Sugars are produced during the Calvin Cycle to store chemical energy. "
            "Some exceptions exist in parasitic plants that do not perform photosynthesis."
        )
        self.ingest(
            doc_id="default-photosynthesis-doc",
            text=default_text,
            metadata={
                "user_id": user_id,
                "filename": "Photosynthesis_Overview.txt",
                "extraction_strategy": "plain_text",
                "asset_prefix": ""
            }
        )

    def search(self, query: str, top_k: int = 5, filter: Optional[dict] = None) -> list:
        user_id = filter.get("user_id") if filter else "test-user-001"
        if not self.docs:
            self._seed_default_document(user_id)

        q_tokens = set(self._tokens(query))
        results = []
        for chunk_id, text, md in self.docs:
            if filter and not all(md.get(k) == v for k, v in filter.items()):
                continue
            d_tokens = Counter(self._tokens(text))
            score = sum(d_tokens[t] for t in q_tokens)
            if score > 0:
                results.append({
                    "text": text,
                    "doc_id": md.get("doc_id", chunk_id),
                    "score": float(score),
                    "metadata": md,
                })
        results.sort(key=lambda r: -r["score"])
        return results[:top_k]
