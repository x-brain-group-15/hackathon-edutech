"""Local chunking strategies for document processing.

Includes:
1. Fixed-size (Sentence boundary-aware with sliding overlap)
2. Structural (Markdown heading-based layout chunking)
3. Local Semantic (Jaccard similarity distance between consecutive sentences)
"""
import re


def chunk_fixed(text: str, size: int = 500, overlap: int = 100) -> list[str]:
    """Splits text by sentence-ish boundaries, grouping them into chunks of ~size characters,

    with a sliding overlap window.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk = []
    current_len = 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue

        # Handle extremely long sentences by splitting them character-wise
        if len(s) > size:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_len = 0
            start = 0
            while start < len(s):
                end = start + size
                chunks.append(s[start:end])
                start += (size - overlap) if (size - overlap) > 0 else size
            continue

        # Check if the sentence fits in the current chunk
        if current_len + len(s) + 1 <= size:
            current_chunk.append(s)
            current_len += len(s) + 1
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk))

            # Sliding overlap: backtrack and include previous sentences that fit the overlap budget
            overlap_chunk = []
            overlap_len = 0
            for prev_s in reversed(current_chunk):
                if overlap_len + len(prev_s) + 1 <= overlap:
                    overlap_chunk.insert(0, prev_s)
                    overlap_len += len(prev_s) + 1
                else:
                    break
            current_chunk = overlap_chunk + [s]
            current_len = overlap_len + len(s) + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks or [text]


def chunk_structural(text: str) -> list[str]:
    """Groups text by Markdown headers (# , ## , ### ).

    Ensures that each section's contents remain in a unified chunk.
    """
    lines = text.split("\n")
    chunks = []
    current_header = ""
    current_content = []

    for line in lines:
        # Check if line matches a Markdown header pattern (# to ######)
        if re.match(r"^#{1,6}\s+", line):
            if current_content or current_header:
                header_prefix = f"{current_header}\n" if current_header else ""
                chunks.append(header_prefix + "\n".join(current_content).strip())
            current_header = line.strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content or current_header:
        header_prefix = f"{current_header}\n" if current_header else ""
        chunks.append(header_prefix + "\n".join(current_content).strip())

    chunks = [c for c in chunks if c.strip()]
    return chunks or [text]


def chunk_semantic(text: str, threshold: float = 0.3) -> list[str]:
    """Cuts text into chunks by calculating local vocabulary Jaccard similarity

    between consecutive sentences. When similarity drops, a new topic is assumed
    and a new chunk starts.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return [text]

    def get_tokens(s: str) -> set[str]:
        return set(re.findall(r"\w+", s.lower()))

    chunks = []
    current_chunk = [sentences[0]]

    for i in range(1, len(sentences)):
        s1 = sentences[i - 1]
        s2 = sentences[i]

        t1 = get_tokens(s1)
        t2 = get_tokens(s2)

        if not t1 or not t2:
            jaccard = 1.0
        else:
            jaccard = len(t1 & t2) / len(t1 | t2)

        dist = 1.0 - jaccard

        # If semantic distance exceeds the threshold, start a new chunk
        if dist > threshold:
            chunks.append(" ".join(current_chunk))
            current_chunk = [s2]
        else:
            current_chunk.append(s2)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
