import os
import wave
from enum import Enum

from anthropic import Anthropic
from dataclasses import dataclass
from dotenv import load_dotenv
import httpx
import json
from openai import OpenAI
from pathlib import Path
from typing import Any, Literal, Optional, Union

load_dotenv()

OpenAIVoice = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

client: Optional[Any] = None
try:
    from elevenlabs import play
    from elevenlabs.client import ElevenLabs

    client = ElevenLabs(timeout=60 * 10)
except ImportError:
    pass

from tag_dialogues import Dialogue


class TTSProvider(Enum):
    ELEVENLABS = "elevenlabs"
    ELEVENLABS_HTTP = "elevenlabs_http"
    OPENAI = "openai"


@dataclass
class Voice:
    voice_id: str
    description: str
    labels: dict
    name: str


def write_audio_to_wav(
    audio_bytes: bytes,
    output_path: Union[str, Path],
    channels: int = 1,
    sample_width: int = 2,
    framerate: int = 44100,
) -> None:
    """
    Write raw audio bytes to a WAV file with specified parameters.

    Args:
        audio_bytes: Raw audio data as bytes
        output_path: Path where the WAV file will be saved
        channels: Number of audio channels (1 for mono, 2 for stereo)
        sample_width: Number of bytes per sample (1, 2, or 4)
        framerate: Sample rate in Hz (e.g., 44100, 48000)

    Raises:
        ValueError: If invalid parameters are provided
        IOError: If there's an error writing the file
    """
    # Validate parameters
    if channels not in [1, 2]:
        raise ValueError("Channels must be 1 (mono) or 2 (stereo)")
    if sample_width not in [1, 2, 4]:
        raise ValueError("Sample width must be 1, 2, or 4 bytes")
    if framerate <= 0:
        raise ValueError("Framerate must be positive")

    try:
        with wave.open(str(output_path), "wb") as wav_file:
            # Set WAV file parameters
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(framerate)

            # Write the audio data
            wav_file.writeframes(audio_bytes)

    except IOError as e:
        raise IOError(f"Error writing WAV file: {str(e)}")


# def generate_audio(dialogues: list[Dialogue], voices: dict[str, Voice]):
#     print(len(dialogues), len(voices.keys()))


def generate_audio_for_dialogues(dialogues: list):
    """Generate audio files for dialogues using ElevenLabs API"""
    output_dir = "./audio-output-py"
    os.makedirs(output_dir, exist_ok=True)

    for i, entry in enumerate(dialogues):
        speaker, text = entry["speaker"], entry["text"]
        try:
            # Split long texts into chunks of roughly 200 words
            chunks = []
            current_chunk = []
            current_words = 0

            for line in text.split("\n"):
                line_words = len(line.split())
                if current_words + line_words > 200:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_words = line_words
                else:
                    current_chunk.append(line)
                    current_words += line_words

            if current_chunk:
                chunks.append("\n".join(current_chunk))

            # Generate audio for each chunk
            for j, chunk in enumerate(chunks):
                print(f"{chunk}")
                # audio = client.generate(
                #     text=chunk,
                #     voice="Chris",
                #     model="eleven_turbo_v2_5"
                # )

                # output_path = f"{output_dir}/{i}-{j}-{speaker}.mp3"
                # write_audio_to_wav(audio, output_path)
                # print(f"Generated audio for {speaker} part {j+1}/{len(chunks)}: {chunk[:50]}...")

        except Exception as e:
            print(f"Failed to generate audio for {speaker}:", e)


# def combine_audio(files: list):


def generate_audio(
    chunk_id: int,
    content_id: int,
    text: str,
    voice: Voice,
    provider: TTSProvider = TTSProvider.ELEVENLABS_HTTP,
):
    output_dir = "audio-output"
    audio_file = Path(output_dir) / f"{chunk_id:04d}" / f"{content_id:04d}.mp3"

    if audio_file.exists():
        return audio_file

    # Ensure parent directory exists
    audio_file.parent.mkdir(parents=True, exist_ok=True)

    if provider == TTSProvider.ELEVENLABS:
        audio = client.generate(  # type: ignore
            text=text,
            voice=voice.name,
            model="eleven_turbo_v2_5",
            request_options={"max_retries": 5},
        )
    elif provider == TTSProvider.ELEVENLABS_HTTP:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice.voice_id}"
        headers = {
            "xi-api-key": os.environ.get("ELEVENLABS_API_KEY", ""),
            "Content-Type": "application/json",
        }
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            # Stability is from 0 to 100
            "voice_settings": {"stability": 0.25, "similarity_boost": 0.81},
        }
        transport = httpx.HTTPTransport(retries=10)
        with httpx.Client(timeout=60.0 * 10, transport=transport) as client:
            response = client.post(url, headers=headers, json=data)
            response.raise_for_status()
            audio = response.content
    else:  # OpenAI
        openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), max_retries=10)
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice.name,  # type: ignore
            input=text,
            response_format="wav",
        )
        audio = response.read()

    write_audio_to_wav(audio, audio_file)
    return audio_file


def get_voices(provider: TTSProvider = TTSProvider.ELEVENLABS_HTTP) -> list[Voice]:
    if provider == TTSProvider.ELEVENLABS:
        voices = client.voices.get_all().voices  # type: ignore
        return [
            Voice(
                voice_id=v.voice_id,
                description=v.description,
                labels=v.labels,
                name=v.name,
            )
            for v in voices
        ]
    elif provider == TTSProvider.ELEVENLABS_HTTP:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": os.environ.get("ELEVENLABS_API_KEY", "")}

        with httpx.Client(
            timeout=30.0, transport=httpx.HTTPTransport(retries=3)
        ) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            voices_data = response.json()["voices"]
        return [
            Voice(
                voice_id=v["voice_id"],
                description=v.get("description", ""),
                labels=v.get("labels", {}),
                name=v["name"],
            )
            for v in voices_data
        ]
    else:
        return [
            Voice(
                voice_id="alloy",
                name="alloy",
                description="A neutral voice with balanced clarity and character",
                labels={"style": "neutral", "age": "young", "gender": "androgynous"},
            ),
            Voice(
                voice_id="echo",
                name="echo",
                description="A deep, resonant voice with a technical tone",
                labels={"style": "serious", "age": "middle", "gender": "male"},
            ),
            Voice(
                voice_id="fable",
                name="fable",
                description="A gentle, warm voice with a mystical quality",
                labels={"style": "whimsical", "age": "young", "gender": "female"},
            ),
            Voice(
                voice_id="onyx",
                name="onyx",
                description="A deep, authoritative voice with gravitas",
                labels={"style": "professional", "age": "mature", "gender": "male"},
            ),
            Voice(
                voice_id="nova",
                name="nova",
                description="An energetic, bright voice with a youthful tone",
                labels={"style": "cheerful", "age": "young", "gender": "female"},
            ),
            Voice(
                voice_id="shimmer",
                name="shimmer",
                description="A clear, optimistic voice with a gentle presence",
                labels={"style": "friendly", "age": "young", "gender": "female"},
            ),
        ]


def assign_voices_to_speakers(speakers: set[str], voices: list[Voice], content: str):
    # use anthropic api to assign a voice that best matches the speaker, based on the content.
    anthropic = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Add NARRATOR to speakers if not present
    speakers_with_narrator = speakers | {"NARRATOR"}

    # Create a prompt for Claude to analyze speakers and match voices
    prompt = f"""Given the following content and list of available voices, assign the most appropriate voice to each speaker based on their characteristics, dialogue style, and personality.

Content with speakers:
{content}

Available voices:
{[f"{v.name}: {v.description}" for v in voices]}

For each speaker below, recommend the best matching voice:
{speakers_with_narrator}

Note: For the NARRATOR, choose a neutral, clear voice suitable for narration (preferably 'alloy' if available).

Format your response as:
<speaker_voice_assignments>
speaker1: voice_name1
speaker2: voice_name2
...
</speaker_voice_assignments>

Do not include any other information in your response, just the speaker name and the voice name, one per line.
"""

    # Get Claude's recommendations
    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0,
        messages=[
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": "<speaker_voice_assignments>"},
        ],
        stop_sequences=["</speaker_voice_assignments>"],
    )

    # Parse the response to get voice assignments
    assignments = {}

    # Parse each line of assignments
    for line in response.content[0].text.split("\n"):  # type: ignore
        if not line.strip():
            continue
        speaker, voice_name = line.split(":")
        speaker = speaker.strip()
        voice_name = voice_name.strip()

        # Find matching voice object
        matching_voice = next((v for v in voices if v.name == voice_name), None)
        if matching_voice:
            assignments[speaker] = matching_voice

    # Fill in any unassigned speakers with random voices
    unassigned = set(speakers_with_narrator) - set(assignments.keys())
    available_voices = [v for v in voices if v not in assignments.values()]

    # If NARRATOR is unassigned, try to use alloy voice first
    if "NARRATOR" in unassigned:
        alloy_voice = next((v for v in voices if v.name == "alloy"), None)
        if alloy_voice:
            assignments["NARRATOR"] = alloy_voice
            unassigned.remove("NARRATOR")
            if alloy_voice in available_voices:
                available_voices.remove(alloy_voice)

    # Log warning
    if unassigned:
        print(f"Warning: {len(unassigned)} speakers were not assigned voices.")

    # Assign remaining speakers
    for speaker in unassigned:
        if available_voices:
            assignments[speaker] = available_voices.pop(0)
        else:
            # If we run out of voices, reuse existing ones
            assignments[speaker] = voices[0]

    return assignments
