"""Regression tests for the terminal chat client."""
import io
import sys
from unittest.mock import patch

sys.path.insert(0, "scripts")

import chat_cli


def run_cli(inputs):
    with patch("builtins.input", side_effect=inputs), \
            patch("sys.stdout", new_callable=io.StringIO) as out, \
            patch.object(chat_cli, "post_json",
                         side_effect=AssertionError("model called!")), \
            patch.object(chat_cli, "post_file",
                         return_value={"image_path": "uploads/x.jpg"}) \
            as upload:
        chat_cli.main(["--session", "cli-test"])
    return out.getvalue(), upload


def test_bare_image_command_never_reaches_model():
    text, upload = run_cli(["/image", "   ", "/quit"])
    assert "Image path:" in text
    assert upload.call_count == 0


def test_quoted_path_is_cleaned():
    text, upload = run_cli(["/image", "'/tmp/room pic.jpg '", "/quit"])
    assert upload.call_count == 1
    assert upload.call_args[0][1] == "/tmp/room pic.jpg"
    assert "attached:" in text
