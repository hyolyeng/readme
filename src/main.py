import asyncio
import datetime
import json
from pathlib import Path
import re
from collections import defaultdict
from dataclasses import asdict
from pydub import AudioSegment
from tqdm import tqdm

from audio_gen import (Voice, assign_voices_to_speakers, generate_audio,
                       get_voices)
from tag_dialogues import Dialogue, split_content_by_speaker, tag_dialogues


def split_into_chunks(content: str, chunk_size: int = 30000) -> list[str]:
    """Break content into roughly equal sized chunks"""
    chunks = []
    current_chunk = []
    current_length = 0

    for line in content.split('\n'):
        line_length = len(line)

        if current_length + line_length > chunk_size and current_chunk:
            # Join current chunk and add to chunks
            chunks.append('\n'.join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(line)
        current_length += line_length

    # Add final chunk if there is one
    if current_chunk:
        chunks.append('\n'.join(current_chunk))

    return chunks


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__dict__"):
            return asdict(obj)
        # Handle other non-serializable types
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


async def main():
    import sys
    if len(sys.argv) < 2:
        print("Please provide an epub file path")
        sys.exit(1)

    file_path = sys.argv[1]
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    use_cache = len(sys.argv) < 3 or sys.argv[2] != '--no-cache'

    content = re.sub(r'-{3,}', '', content)
    # Remove extra newlines
    content = re.sub(r'\n{3,}', '\n\n', content)

    chunks = split_into_chunks(content)

    speakers_to_voices: dict[str, Voice] = dict()
    # Track the last chunk index where each speaker was seen
    speaker_last_seen: dict[str, int] = defaultdict(int)

    START_INDEX = 0

    all_voices = get_voices()

    audio_paths = []

    for i, chunk in tqdm(enumerate(chunks), total=len(chunks)):
        if i < START_INDEX:
            continue

        if i > 4:
            return

        result_cache_file = f"result-{i}.json"
        if use_cache:
            try:
                with open(f"cache/{result_cache_file}", "r") as f:
                    # generate audio
                    result = json.load(f)
                    content = [Dialogue(**d) for d in result["content"]]
                    voices = {k: Voice(**v) for k,v in result["voices"].items()}
                    generate_audio(content, voices)
                    return
            except Exception as e:
                print(f"no cache available for chunk {i}")

        with open("chunk.txt", "w") as f:
            f.write(chunk)
        dialogues = tag_dialogues(chunk, use_cache=use_cache)

        speakers = set(d.speaker for d in dialogues)
        
        # Update last seen index for current speakers
        for speaker in speakers:
            speaker_last_seen[speaker] = i

        new_speakers = speakers - speakers_to_voices.keys()
        available_voices = [v for v in all_voices if v not in speakers_to_voices.values()]

        if len(available_voices) < len(new_speakers):
            # Get speakers sorted by last seen chunk (oldest first)
            lru_speakers = sorted(
                speakers_to_voices.keys(),
                key=lambda s: speaker_last_seen[s]
            )
            
            # Remove oldest speakers until we have enough voices
            for old_speaker in lru_speakers:
                if len(available_voices) >= len(new_speakers) * 2 + 5: # buffer
                    break
                    
                freed_voice = speakers_to_voices.pop(old_speaker)
                available_voices.append(freed_voice)

        new_speaker_assignments = assign_voices_to_speakers(new_speakers, available_voices, chunk)
        speakers_to_voices.update(new_speaker_assignments)

        content_split = split_content_by_speaker(content=chunk, dialogues=dialogues)

        with open(f"result-{i}.json", "w") as f:
            json.dump({"content": content_split, "voices": speakers_to_voices}, f, cls=DataclassJSONEncoder)

        for j, content in enumerate(content_split):
            text = content["text"]
            speaker = content["speaker"]
            voice = speakers_to_voices[speaker]

            audio_paths.append(generate_audio(i, j, text, voice))

        break

    # Combine all audio files into a single MP3
    if audio_paths:
        combined = AudioSegment.from_mp3(str(audio_paths[0]))
        for audio_path in audio_paths[1:]:
            next_segment = AudioSegment.from_mp3(str(audio_path))
            combined += next_segment
            
        output_dir = "audio-output"
        final_path = Path(output_dir) / f"{i:04d}_combined.mp3"
        final_path.parent.mkdir(parents=True, exist_ok=True)
        combined.export(str(final_path), format="mp3")

    return


if __name__ == "__main__":
    asyncio.run(main())
