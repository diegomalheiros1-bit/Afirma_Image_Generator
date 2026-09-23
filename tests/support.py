import io
import os
import unittest
from unittest.mock import patch
from PIL import Image


def png_bytes():
    stream = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(stream, format="PNG")
    return stream.getvalue()


class IsolatedTest(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            "IMAGE_PROVIDER": "simulation", "MAX_JOBS_PER_RUN": "10", "MAX_IMAGES_PER_RUN": "20",
            "FIRST_RUN_SAFE_MODE": "NAO", "PYTHON_DOTENV_DISABLED": "1",
        }, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        dotenv = patch("main.dotenv_values", return_value={})
        dotenv.start()
        self.addCleanup(dotenv.stop)
        # Fail the test if any code tries to instantiate a network client.
        client = patch("openai.OpenAI", side_effect=AssertionError("Network client forbidden in tests"))
        client.start()
        self.addCleanup(client.stop)
