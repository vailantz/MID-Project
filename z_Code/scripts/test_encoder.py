"""Check query text preparation without downloading or loading model weights."""

import unittest
from unittest.mock import Mock

try:
    from encoder import Encoder, QUERY_INSTRUCTION
except ModuleNotFoundError as error:
    if error.name not in {"torch", "transformers", "huggingface_hub"}:
        raise
    Encoder = None


@unittest.skipIf(Encoder is None, "GPU Python packages required")
class QueryText(unittest.TestCase):
    def test_query_uses_the_same_text_cleaning_as_review_documents(self):
        encoder = object.__new__(Encoder)
        encoder.encode = Mock(return_value=[[1.0]])
        self.assertEqual(encoder.query(" <b>pink</b>  house &amp; garden "), [1.0])
        encoder.encode.assert_called_once_with([
            f"Instruct: {QUERY_INSTRUCTION}\nQuery:pink house & garden"
        ])


if __name__ == "__main__":
    unittest.main()
