import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.append(str(Path(__file__).parent.parent))

# Mock required modules
sys.modules["audio_gen"] = MagicMock()
sys.modules["tag_dialogues"] = MagicMock()

from src.main import split_into_chunks


def test_split_into_chunks():
    # Test basic splitting
    content = "line1\n" * 10000
    chunks = split_into_chunks(content, chunk_size=10)
    assert len(chunks) > 1
    assert all(len(chunk) <= 10 for chunk in chunks)

    # Test preserving line breaks
    content = "line1\nline2\nline3"
    chunks = split_into_chunks(content, chunk_size=11)
    assert chunks[0] == "line1\nline2"
    assert chunks[1] == "line3"

    # Test handling empty input
    assert split_into_chunks("") == []

    # Test single chunk case
    content = "short text"
    chunks = split_into_chunks(content, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == content
