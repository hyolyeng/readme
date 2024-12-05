import asyncio
import datetime
import defopt
import json
import re

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from pydub import AudioSegment
from tqdm import tqdm
from typing import Any, Optional

from audio_gen import Voice, assign_voices_to_speakers, generate_audio, get_voices
from tag_dialogues import Dialogue, split_content_by_speaker, tag_dialogues


def split_into_chunks(content: str, chunk_size: int = 30000) -> list[str]:
    """Break content into roughly equal sized chunks.

    Args:
        content: The text content to split into chunks
        chunk_size: Maximum size of each chunk in characters

    Returns:
        List of content chunks, each approximately chunk_size characters
    """
    chunks = []
    current_chunk = []
    current_length = 0

    for line in content.split("\n"):
        line_length = len(line)

        if current_length + line_length > chunk_size and current_chunk:
            # Join current chunk and add to chunks
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(line)
        current_length += line_length

    # Add final chunk if there is one
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


class DataclassJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for serializing dataclass objects.

    Extends the default JSON encoder to handle dataclasses and datetime objects.
    """

    def default(self, o: Any) -> Any:
        """Convert object to a JSON serializable format.

        Args:
            o: The object to serialize

        Returns:
            JSON serializable representation of the object
        """
        if hasattr(o, "__dict__"):
            return asdict(o)
        # Handle other non-serializable types
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


@dataclass
class AudioGenConfig:
    """Configuration for audio generation."""

    input_file: Path
    """Path to the input text file"""
    use_cache: bool = True
    """Whether to use cached results"""


async def main(*, input_file: Path, use_cache: bool = True, debug: bool = True) -> None:
    """Main entry point for the audio generation pipeline.

    Processes an input text file by:
    1. Splitting content into manageable chunks
    2. Identifying speakers and assigning voices
    3. Generating audio for each chunk
    4. Combining audio files into final output

    Args:
        input_file: Path to input text file
        use_cache: If False, skip using cached results
    """
    content = input_file.read_text(encoding="utf-8")

    content = re.sub(r"-{3,}", "", content)
    # Remove extra newlines
    content = re.sub(r"\n{3,}", "\n\n", content)

    chunks = split_into_chunks(content)

    speakers_to_voices: dict[str, Voice] = dict()
    # Track the last chunk index where each speaker was seen
    speaker_last_seen: dict[str, int] = defaultdict(int)

    START_INDEX = 0

    all_voices = get_voices()

    audio_paths = []
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    chunk_index: Optional[int] = None

    for i, chunk in tqdm(enumerate(chunks), total=len(chunks)):
        chunk_index = i
        if i < START_INDEX:
            continue

        # Stop early if debug mode is enabled
        if debug and i > 4:
            print(f"Stopping because {debug=}")
            return

        result_cache_file = cache_dir / f"result-{i}.json"
        if use_cache and result_cache_file.exists():
            try:
                result = json.loads(result_cache_file.read_text())
                content = [Dialogue(**d) for d in result["content"]]
                voices = {k: Voice(**v) for k, v in result["voices"].items()}
                generate_audio(
                    chunk_id=i,
                    content_id=0,
                    text=content[0].text,
                    voice=voices[content[0].speaker],
                )
                return
            except Exception as e:
                print(f"no cache available for chunk {i}")

        chunk_file = Path("chunk.txt")
        chunk_file.write_text(chunk)
        dialogues = tag_dialogues(chunk, use_cache=use_cache)

        speakers = set(d.speaker for d in dialogues)

        # Update last seen index for current speakers
        for speaker in speakers:
            speaker_last_seen[speaker] = i

        new_speakers = speakers - speakers_to_voices.keys()
        available_voices = [
            v for v in all_voices if v not in speakers_to_voices.values()
        ]

        if len(available_voices) < len(new_speakers):
            # Get speakers sorted by last seen chunk (oldest first)
            lru_speakers = sorted(
                speakers_to_voices.keys(), key=lambda s: speaker_last_seen[s]
            )

            # Remove oldest speakers until we have enough voices
            for old_speaker in lru_speakers:
                if len(available_voices) >= len(new_speakers) * 2 + 5:  # buffer
                    break

                freed_voice = speakers_to_voices.pop(old_speaker)
                available_voices.append(freed_voice)

        new_speaker_assignments = assign_voices_to_speakers(
            new_speakers, available_voices, chunk
        )
        speakers_to_voices.update(new_speaker_assignments)

        # Convert dialogues to list of dicts for split_content_by_speaker
        content_split = split_content_by_speaker(content=chunk, dialogues=dialogues)

        result_file = Path(f"result-{i}.json")
        result_file.write_text(
            json.dumps(
                {"content": content_split, "voices": speakers_to_voices},
                cls=DataclassJSONEncoder,
            )
        )

        for j, content in enumerate(content_split):
            text = content.text
            speaker = content.speaker
            voice = speakers_to_voices[speaker]

            audio_paths.append(
                generate_audio(chunk_id=i, content_id=j, text=text, voice=voice)
            )

        break

    # Combine all audio files into a single MP3
    if audio_paths and chunk_index is not None:
        combined = AudioSegment.from_mp3(str(audio_paths[0]))
        for audio_path in audio_paths[1:]:
            next_segment = AudioSegment.from_mp3(str(audio_path))
            combined += next_segment

        output_dir = Path("audio-output")
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = output_dir / f"{chunk_index:04d}_combined.mp3"
        combined.export(str(final_path), format="mp3")

    return


if __name__ == "__main__":
    asyncio.run(defopt.run(main, parsers={Path: Path}))
