"""Check query-service reuse and validation without loading the GPU model."""

import threading
import unittest
from unittest.mock import Mock, patch
from http.server import HTTPServer

import requests

import query_encoder


class Vector:
    def tolist(self):
        return [1.0, 0.0]


class Encoder:
    def __init__(self):
        self.queries = []

    def query(self, text):
        self.queries.append(text)
        return Vector()


class QueryService(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), query_encoder.Handler)
        self.encoder = self.server.encoder = Encoder()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.patch = patch.object(query_encoder, "URL", self.url)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_two_queries_reuse_one_encoder(self):
        pid = query_encoder.health()["pid"]
        self.assertEqual(query_encoder.query_vector("quiet"), [1.0, 0.0])
        self.assertEqual(query_encoder.query_vector("central"), [1.0, 0.0])
        self.assertIs(self.server.encoder, self.encoder)
        self.assertEqual(self.encoder.queries, ["quiet", "central"])
        self.assertEqual(query_encoder.health()["pid"], pid)

    def test_invalid_requests_leave_encoder_available(self):
        for body in ({"text": " "}, {"text": 12}, {}, {"text": None}):
            response = requests.post(self.url + "/encode", json=body, timeout=2)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(query_encoder.query_vector("valid"), [1.0, 0.0])

    def test_mismatched_model_is_rejected(self):
        with patch.object(query_encoder, "CONTRACT", {"model": "other"}):
            # The client validates the configuration advertised by the service.
            with patch.object(query_encoder.requests, "get") as get:
                get.return_value.json.return_value = {"contract": {"model": "original"}}
                with self.assertRaisesRegex(RuntimeError, "different model"):
                    query_encoder.health()

    def test_shutdown_requires_three_consecutive_failures(self):
        finished = Mock()
        finished.wait.return_value = False
        server = Mock()
        failure = requests.ConnectionError("Elasticsearch stopped")
        with patch.object(query_encoder, "es", side_effect=[failure, {}, failure, failure, failure]) as check:
            query_encoder.watch_elasticsearch(server, finished)
        self.assertEqual(check.call_count, 5)
        server.shutdown.assert_called_once_with()
        self.assertTrue(all(call.args == (5,) for call in finished.wait.call_args_list))


if __name__ == "__main__":
    unittest.main()
