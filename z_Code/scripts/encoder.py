"""Qwen document/query encoding with the same pooling and normalization rules."""

import html
import re

import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer
from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

MODEL_ID = "Qwen/Qwen3-Embedding-4B"
MODEL_REVISION = "5cf2132abc99cad020ac570b19d031efec650f2b"
DIMENSIONS = 1024
MAX_TOKENS = 8192
BATCH_SIZE = 64
TOKEN_BUDGET = 16384
READ_BATCH_SIZE = 1024
QUERY_INSTRUCTION = (
    "Given a travel accommodation search query, retrieve relevant guest reviews."
)
VECTOR_MAPPING = {
    "type": "dense_vector",
    "dims": DIMENSIONS,
    "index": True,
    "similarity": "cosine",
    "index_options": {"type": "int8_hnsw"},
}
CONTRACT = {
    "model": MODEL_ID,
    "revision": MODEL_REVISION,
    "dimensions": DIMENSIONS,
    "max_tokens": MAX_TOKENS,
    "pooling": "last_token",
    "normalization": "L2 after dimension truncation",
    "dtype": "bfloat16",
    "attention": "sdpa",
    "padding_side": "left",
    "text_processing": "HTML tags removed; entities decoded; whitespace collapsed",
    "query_instruction": QUERY_INSTRUCTION,
}


def clean_text(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text))).strip()


class Encoder:
    def __init__(self):
        if not torch.cuda.is_available():
            raise RuntimeError(
                "A CUDA-enabled PyTorch installation is required for this configuration."
            )
        self.device = "cuda"
        try:
            path = snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_files_only=True)
        except LocalEntryNotFoundError:
            path = snapshot_download(MODEL_ID, revision=MODEL_REVISION)
        self.tokenizer = AutoTokenizer.from_pretrained(path, padding_side="left")
        self.model = (
            AutoModel.from_pretrained(
                path, torch_dtype=torch.bfloat16, attn_implementation="sdpa"
            )
            .eval()
            .to(self.device)
        )

    def encode(self, texts):
        tokens = self.tokenizer(texts, padding=True, truncation=False, return_tensors="pt")
        if tokens["input_ids"].shape[1] > MAX_TOKENS:
            raise ValueError(
                f"Text exceeds {MAX_TOKENS} tokens. Increase the limit explicitly; no text was silently truncated."
            )
        tokens = tokens.to(self.device)
        try:
            with torch.inference_mode():
                hidden = self.model(**tokens, use_cache=False).last_hidden_state
                vectors = F.normalize(hidden[:, -1, :DIMENSIONS].float(), p=2, dim=1)
                if not torch.isfinite(vectors).all():
                    raise RuntimeError("Model produced a non-finite embedding.")
            return vectors.cpu().numpy()
        except torch.cuda.OutOfMemoryError:
            if len(texts) == 1:
                raise
            del tokens
            torch.cuda.empty_cache()
            import numpy as np

            middle = len(texts) // 2
            return np.concatenate([self.encode(texts[:middle]), self.encode(texts[middle:])])

    def query(self, text):
        return self.encode([f"Instruct: {QUERY_INSTRUCTION}\nQuery:{text}"])[0]

    def batches(self, records):
        # Length sorting reduces padding; the token budget bounds GPU activation memory.
        lengths = [
            len(ids)
            for ids in self.tokenizer([r[1] for r in records], truncation=False)["input_ids"]
        ]
        pending = []
        for position in sorted(range(len(records)), key=lambda i: lengths[i]):
            if pending and (
                len(pending) >= BATCH_SIZE
                or (len(pending) + 1) * lengths[position] > TOKEN_BUDGET
            ):
                yield pending
                pending = []
            pending.append(position)
        if pending:
            yield pending
