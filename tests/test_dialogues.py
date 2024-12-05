import json
import pytest
from src.tag_dialogues import split_content_by_speaker, Dialogue


def normalize_quotes(data):
    if isinstance(data[0], dict):
        return [
            {
                "speaker": item["speaker"],
                "text": item["text"].replace('"', "'").replace('"', "'"),
            }
            for item in data
        ]
    else:
        return [
            {
                "speaker": item.speaker,
                "text": item.text.replace('"', "'").replace('"', "'"),
            }
            for item in data
        ]


@pytest.fixture
def complex_dialogue():
    return {
        "content": '"I need help," she said desperately. "Please help me now!"',
        "dialogues": [
            Dialogue(speaker="ALICE", text="I need help"),
            Dialogue(speaker="ALICE", text="Please help me now!"),
        ],
        "expected": [
            Dialogue(speaker="ALICE", text="I need help"),
            Dialogue(speaker="NARRATOR", text="she said desperately."),
            Dialogue(speaker="ALICE", text="Please help me now!"),
        ],
    }


@pytest.fixture
def narration_first_dialogue():
    return {
        "content": 'The sun was setting. "Hello," said John. "How are you?" He was so good.',
        "dialogues": [
            Dialogue(speaker="John", text="Hello"),
            Dialogue(speaker="John", text="How are you?"),
        ],
        "expected": [
            Dialogue(speaker="NARRATOR", text="The sun was setting."),
            Dialogue(speaker="John", text="Hello"),
            Dialogue(speaker="NARRATOR", text="said John."),
            Dialogue(speaker="John", text="How are you?"),
            Dialogue(speaker="NARRATOR", text="He was so good."),
        ],
    }


@pytest.fixture
def simple_dialogue():
    return {
        "content": '"Hello there," said John. "How are you today?"',
        "dialogues": [
            Dialogue(speaker="John", text="Hello there,"),
            Dialogue(speaker="John", text="How are you today?"),
        ],
        "expected": [
            Dialogue(speaker="John", text="Hello there,"),
            Dialogue(speaker="NARRATOR", text="said John."),
            Dialogue(speaker="John", text="How are you today?"),
        ],
    }


@pytest.fixture
def chunk_dialogue():
    with open("tests/fixtures/chunk_in.txt", "r", encoding="utf-8") as f:
        content = f.read().replace('"', "'").replace('"', "'")

    with open("tests/fixtures/dialogues.json", "r", encoding="utf-8") as f:
        dialogues_json = json.load(f)
        dialogues = [
            Dialogue(speaker=d["speaker"], text=d["text"]) for d in dialogues_json
        ]

    with open("tests/fixtures/expected.json", "r", encoding="utf-8") as f:
        expected_json = json.load(f)
        expected = [
            Dialogue(speaker=d["speaker"], text=d["text"]) for d in expected_json
        ]

    return {"content": content, "dialogues": dialogues, "expected": expected}


def test_complex_text_repetition(complex_dialogue):
    result = split_content_by_speaker(
        complex_dialogue["content"], complex_dialogue["dialogues"]
    )
    assert result == complex_dialogue["expected"]


def test_no_text_repetition(simple_dialogue):
    result = split_content_by_speaker(
        simple_dialogue["content"], simple_dialogue["dialogues"]
    )
    assert result == simple_dialogue["expected"]


def test_content_starts_with_narration(narration_first_dialogue):
    result = split_content_by_speaker(
        narration_first_dialogue["content"], narration_first_dialogue["dialogues"]
    )
    assert result == narration_first_dialogue["expected"]


def test_split_content_by_speaker(chunk_dialogue):
    result = split_content_by_speaker(
        chunk_dialogue["content"], chunk_dialogue["dialogues"]
    )

    # with open("test-output.json", "w") as f:
    #     result_json = [{"speaker": d.speaker, "text": d.text} for d in result]
    #     json.dump(result_json, f)

    norm_result = normalize_quotes(result)
    norm_expected = normalize_quotes(chunk_dialogue["expected"])

    assert norm_result == norm_expected
