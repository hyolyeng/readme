# Epub Audio Generator

A hybrid TypeScript/Python application that converts epub books into audio using ElevenLabs text-to-speech.

## Features

- Epub file parsing and text extraction
- Dialogue detection and tagging
- Audio generation via ElevenLabs API
- Supports both TypeScript and Python components

## Prerequisites

- Node.js and npm
- Python 3.11+
- ElevenLabs API key

## Installation

Install TypeScript dependencies:

```bash
npm i
```

Install Python dependencies:

```bash
brew install uv wget
uv init -p 3.12
uv pip install -e .
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin

```

## Usage

Start the application:

```bash
npm start
```

Build TypeScript:

```bash
npm run build
```

Run Python tests:

```bash
python -m pytest
```

Run python:

```bash
uv run src/main.py -i worth_the_candle.txt
```

## Project Structure

- `src/` - Source code
  - TypeScript files (.ts) - Audio generation and epub reading
  - Python files (.py) - Text processing and dialogue tagging
- `tests/` - Test files and fixtures
- `cache/` - Generated audio cache

## License

ISC
