import asyncio
import datetime
import pprint
import defopt
import json
import re

from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from pydub import AudioSegment
from tqdm import tqdm
from typing import Any

from audio_gen import Voice, assign_voices_to_speakers, generate_audio, get_voices
from tag_dialogues import Dialogue, split_content_by_speaker, tag_dialogues


def combine_audio_files(audio_paths: list[Path], chunk_id: int) -> None:
    """Combine multiple audio files into a single MP3 file.
    
    Args:
        audio_paths: List of paths to audio files to combine
        chunk_id: ID of the current chunk for naming the output file
    """
    output_dir = Path("audio-output")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / f"{chunk_id:04d}_combined.mp3"

    if final_path.exists() or not audio_paths:
        return
    combined = AudioSegment.empty()
    for audio_path in audio_paths:
        combined += AudioSegment.from_mp3(audio_path)
    combined.export(final_path, format="mp3")

def split_into_chunks(content: str, chunk_size: int = 20000) -> list[str]:
    """Break content into roughly equal sized chunks.

    Args:
        content: The text content to split into chunks
        chunk_size: Maximum size of each chunk in characters

    Returns:
        List of content chunks, each approximately chunk_size characters
    """
    if not content:
        return []

    chunks = []
    lines = content.split("\n")
    current_chunk = []
    current_size = 0

    for i, line in enumerate(lines):
        # Calculate size including newline
        line_size = len(line)
        if current_chunk:  # Add newline if not first line in chunk
            line_size += 1

        assert line_size <= chunk_size, f"Line {i} is too long: {line_size}"

        # Try to add line to current chunk
        if current_size + line_size <= chunk_size:
            current_chunk.append(line)
            current_size += line_size
        else:
            # Start new chunk with this line
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_size = line_size

    # Add final chunk if there is one
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


class DataclassJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for serializing dataclass objects.

    Extends the default JSON encoder to handle dataclasses
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
        return super().default(o)


@dataclass
class AudioGenConfig:
    """Configuration for audio generation."""

    input_file: Path
    """Path to the input text file"""
    use_cache: bool = True
    """Whether to use cached results"""


async def main(
    *,
    input_file: Path,
    use_cache: bool = True,
    debug: bool = True,
    start_index: int = 0,
) -> None:
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

    all_voices = get_voices()

    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)

    for i, chunk in tqdm(enumerate(chunks), total=len(chunks)):
        audio_paths = []
        if i < start_index:
            continue

        result_cache_file = cache_dir / f"result-{i}.json"
        if use_cache and result_cache_file.exists():
            result = json.loads(result_cache_file.read_text())
            content_split = [Dialogue(**d) for d in result["content"]]
            speakers_to_voices = {k: Voice(**v) for k, v in result["voices"].items()}
            speaker_last_seen.update(result.get("speaker_last_seen", {}))
        else:
            # # Write chunk to file for debugging. Not used elsewhere.
            # chunk_file = Path("chunk.txt")
            # chunk_file.write_text(chunk)
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
            pprint.pprint({k: v.name for k, v in speakers_to_voices.items()})

            # Convert dialogues to list of dicts for split_content_by_speaker
            content_split = split_content_by_speaker(content=chunk, dialogues=dialogues)

            result_cache_file.write_text(
                json.dumps(
                    {"content": content_split, "voices": speakers_to_voices, "speaker_last_seen": speaker_last_seen.__dict__},
                    cls=DataclassJSONEncoder,
                )
        )

        for j, content in enumerate(tqdm(content_split, desc=f"Chunk {i}")):
            text = content.text
            speaker = content.speaker
            voice = speakers_to_voices[speaker]

            audio_paths.append(
                generate_audio(chunk_id=i, content_id=j, text=text, voice=voice)
            )

        # Combine all audio files into a single MP3 per chunk
        combine_audio_files(audio_paths, i)

        # Stop early if debug mode is enabled
        if debug:
            print(f"Stopping because {debug=}")
            break


if __name__ == "__main__":
    asyncio.run(defopt.run(main, parsers={Path: Path}))
