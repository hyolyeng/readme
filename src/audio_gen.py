from dataclasses import dataclass
from anthropic import Anthropic
from elevenlabs import play
from elevenlabs.client import ElevenLabs
import wave
from typing import Union
from pathlib import Path
import os

from tag_dialogues import Dialogue

client = ElevenLabs(timeout=60*10)

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
    framerate: int = 44100
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
        with wave.open(str(output_path), 'wb') as wav_file:
            # Set WAV file parameters
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(framerate)
            
            # Write the audio data
            wav_file.writeframes(audio_bytes)
            
    except IOError as e:
        raise IOError(f"Error writing WAV file: {str(e)}")
    
def generate_audio(dialogues: list[Dialogue], voices: dict[str, Voice]):
    print(len(dialogues), len(voices.keys()))

def generate_audio_for_dialogues(dialogues: list):
    """Generate audio files for dialogues using ElevenLabs API"""
    output_dir = './audio-output-py'
    os.makedirs(output_dir, exist_ok=True)

    for i, entry in enumerate(dialogues):
        speaker, text = entry["speaker"], entry["text"]
        try:
            # Split long texts into chunks of roughly 200 words
            chunks = []
            current_chunk = []
            current_words = 0
            
            for line in text.split('\n'):
                line_words = len(line.split())
                if current_words + line_words > 200:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_words = line_words
                else:
                    current_chunk.append(line)
                    current_words += line_words
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))

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


def generate_audio(chunk_id: int, content_id: int, text: str, voice: Voice):
    # might need to split the text into chunks
    # num_words = len(text.split())
    # if num_words > 200:
    #     # do chunking, and process
    #     pass

    # else, just generate audio
    audio = client.generate(
        text=text,
        voice=voice.name,
        model="eleven_turbo_v2_5",
        request_options={"max_retries": 5}
    )

    output_dir = "audio-output"
    audio_file = Path(output_dir) / f"{chunk_id:04d}" / f"{content_id:04d}.mp3"

    if audio_file.exists():
        return audio_file

    # Ensure parent directory exists
    audio_file.parent.mkdir(parents=True, exist_ok=True)
    write_audio_to_wav(audio, audio_file)
    return audio_file

def get_voices() -> list[Voice]:
    voices = client.voices.get_all().voices
    return [Voice(voice_id=v.voice_id, description=v.description, labels=v.labels, name=v.name) for v in voices]


def assign_voices_to_speakers(speakers: set[str], voices: list[Voice], content: str):
    # use anthropic api to assign a voice that best matches the speaker, based on the content.
    anthropic = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    # Create a prompt for Claude to analyze speakers and match voices
    prompt = f"""Given the following content and list of available voices, assign the most appropriate voice to each speaker based on their characteristics, dialogue style, and personality.

Content with speakers:
{content}

Available voices:
{[f"{v.name}: {v.description}" for v in voices]}

For each speaker below, recommend the best matching voice:
{speakers}

Format your response as:
<speaker_voice_assignments>
speaker1: voice_name1
speaker2: voice_name2
...
</speaker_voice_assignments>
"""

    # Get Claude's recommendations
    response = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0,
        messages=[
            {
                "role": "user", 
                "content": prompt
            }
        ]
    )

    # Parse the response to get voice assignments
    assignments = {}
    assignment_text = response.content[0].text

    print(assignment_text)
    
    # Extract content between tags
    if '<speaker_voice_assignments>' in assignment_text:
        assignments_section = assignment_text.split('<speaker_voice_assignments>')[1].split('</speaker_voice_assignments>')[0].strip()
        
        # Parse each line of assignments
        for line in assignments_section.split('\n'):
            if ':' in line:
                speaker, voice_name = line.split(':')
                speaker = speaker.strip()
                voice_name = voice_name.strip()
                
                # Find matching voice object
                matching_voice = next((v for v in voices if v.name == voice_name), None)
                if matching_voice:
                    assignments[speaker] = matching_voice

    # Fill in any unassigned speakers with random voices
    unassigned = set(speakers) - set(assignments.keys())
    available_voices = [v for v in voices if v not in assignments.values()]
    
    for speaker in unassigned:
        if available_voices:
            assignments[speaker] = available_voices.pop(0)
        else:
            # If we run out of voices, reuse existing ones
            assignments[speaker] = voices[0]

    return assignments
