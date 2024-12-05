from dataclasses import dataclass
import hashlib
import os
import re

from anthropic import Anthropic


@dataclass
class Dialogue:
    speaker: str
    text: str


def _find_dialogue_in_content(content: str, current_pos: int, dialogue: Dialogue):
    dialogue_text = clean_text(dialogue.text)
    dialogue_words = dialogue_text.split(" ")

    # Try progressively shorter sequences of words to find the dialogue
    for curr in range(len(dialogue_words) - 1, 0, -1):
        search = " ".join(dialogue_words[0:curr])
        dialogue_pos = content.find(search, current_pos)
        results = []
        
        if dialogue_pos > current_pos:
            # add narration before this dialogue
            narration = content[current_pos:dialogue_pos].strip("\"").strip("'").strip()
            if narration:
                results.append(Dialogue(speaker="NARRATOR", text=narration))

            # add the dialogue
            results.append(Dialogue(speaker=dialogue.speaker, text=search))

            # get the in-between narration
            remainder = " ".join(dialogue_words[curr:])
            remainder_pos = content.find(remainder, dialogue_pos)
            narration = content[dialogue_pos:remainder_pos].strip("\"").strip("'").strip()
            if narration:
                results.append(Dialogue(speaker="NARRATOR", text=narration))
            
            results.append(Dialogue(speaker=dialogue.speaker, text=remainder))
            return results, remainder_pos + len(remainder)
    breakpoint()
    raise Exception(f"no matching dialogue: {dialogue.text}, {current_pos}, {content[current_pos:10]}")


def tag_dialogues(content: str, use_cache=True) -> list[Dialogue]:
    """Use Claude to identify speakers and tag dialogue"""
    anthropic = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    # Generate hash of content for caching
    
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    cache_file = f"anthropic-response-{content_hash}.txt"

    result = None
    if use_cache:
        try:
            with open(f"cache/{cache_file}", "r") as f:
                result = f.read()
        except Exception as e:
            result = None
    
    if not result:
        msg = anthropic.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=8192,
            temperature=0,
            system="""You are an AI assistant specialized in preparing text files for conversion into multi-voice audiobooks. Your primary task is to extract all spoken dialogue in the given text and tag them with the correct speaker names. This will enable audiobook creation software to assign different voices to each character. Narration will be determined in a post-processing step.

Please follow these steps to analyze the content and tag the dialogues:

1. Read through the entire content carefully.
2. Identify all speakers present in the text and create a list of unique speaker names.
3. Identify all instances of dialogue in the text.
4. For each piece of dialogue, determine which speaker is talking.
5. Enclose each piece of dialogue in XML tags with the speaker's name as the tag name.
6. If a speaker cannot be determined, use <UNKNOWN_SPEAKER> tags.
7. Do not tag narration or non-dialogue text. Omit it from the output.
8. If the content is very lengthy, process it in manageable chunks to ensure all conversations are tagged without truncation.
9. Speaker identifier should be stable, even if the content refers to them by nicknames or aliases.
10. If there is narrations such as "he said" in between dialogue, make sure to split the dialogue to multiple dialogue outputs.""",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """<examples>
<example>
<CONTENT>
"Help me," cried Syni. "I need a help."
</CONTENT>
<ideal_output>
<scratchpad>
Syni
</scratchpad>
<tagged_content>
<Syni>"Help me,"</Syni>
<Syni>"I need a help."</Syni>
</tagged_content>
</ideal_output>
</example>
<example>
<CONTENT>
The afternoon sun cast long shadows through the library windows as John and Mary's voices echoed softly off the oak-paneled walls.
"Hello, how are you today?" John's warm greeting carried across the space between them, his eyes crinkling at the corners with genuine warmth.
Mary looked up from the leather-bound book she'd been studying, tucking a stray strand of hair behind her ear. "I'm doing well, thank you. How about you?" Her voice was gentle, matching the hushed atmosphere of their surroundings.
"I'm great, thanks for asking." John's response came with an easy smile as he settled into one of the oversized armchairs nearby.
The peaceful moment was suddenly interrupted by a harsh whisper that seemed to come from the shadows between the towering bookshelves. "Who goes there?" The mysterious voice sent a chill through the air, causing both John and Mary to freeze in place.
</CONTENT>
<ideal_output>
<scratchpad>
John
Mary
</scratchpad>
<tagged_content>
<John>"Hello, how are you today?"</John>
<Mary>"I'm doing well, thank you. How about you?"</Mary>
<John>"I'm great, thanks for asking."</John>
<UNKNOWN_SPEAKER>"Who goes there?"</UNKNOWN_SPEAKER>
</tagged_content>
</ideal_output>
</example>
</examples>

                        """
                        },
                        {
                            "type": "text",
                            "text": f"""Here is the content of the file that needs to be processed:

<content>
{content}
</content>

Before you begin tagging, wrap your analysis inside <scratchpad> tags. This analysis should contain a list of all unique speakers you've identified in the text.

After your analysis, present the fully tagged content within <tagged_content> tags. Remember to maintain the original structure and formatting of the text, only adding the speaker tags around the dialogue portions.

Important:
1. Ensure that ALL dialogues are tagged, even if the content is very long. Process the content in chunks if necessary to avoid truncation. INCLUDE MULTIPLE SEPARATE TAGS even if they are from the same speaker. DO NOT merge tags."""
                        }
                    ]
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "<scratchpad>"
                        }
                    ]
                }
            ])

        result = msg.content[0].text

        with open(cache_file, "w") as f:
            f.write(result)

    # Extract content between <tagged_content> tags
    tagged_content = result.split('<tagged_content>')[
        1].split('</tagged_content>')[0].strip()

    # Find all dialogue tags with content
    dialogues = []
    pattern = r'<([^>]+)>"([^"]+)"</\1>'

    for match in re.finditer(pattern, tagged_content):
        speaker = match.group(1)
        text = match.group(2)
        dialogues.append(Dialogue(speaker=speaker, text=text))
        
    return dialogues


def clean_text(text):
    """
    Replace common problematic Unicode characters with ASCII equivalents
    """
    replacements = {
        '\u201c': '"',  # Opening double quote
        '\u201d': '"',  # Closing double quote
        '\u2018': "'",  # Opening single quote
        '\u2019': "'",  # Closing single quote
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
    }
    
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    return text


def split_content_by_speaker(content: str, dialogues: list[dict]) -> list[dict]:
    """
    Split content into list of dialogues, where the non-tagged narration is tagged with speaker NARRATOR.
    """
    result = []
    current_pos = 0

    content = clean_text(content)

    for dialogue in dialogues:
        # breakpoint()
        dialogue_text = clean_text(dialogue.text)
        
        # Find position of this dialogue in content
        dialogue_pos = content.find(dialogue_text, current_pos)
        
        if dialogue_pos == -1:
            to_add, new_pos = _find_dialogue_in_content(content, current_pos, dialogue)
            result.extend(to_add)
            current_pos = new_pos
            continue
            
        # Add any narration before this dialogue
        if dialogue_pos > current_pos:
            narration = content[current_pos:dialogue_pos].strip("\"").strip("'").strip()
            if narration:
                result.append(Dialogue(speaker="NARRATOR", text=narration))
        
        # Add the dialogue
        result.append(dialogue)
        
        current_pos = dialogue_pos + len(dialogue_text)
    
    # Add any remaining content as narration
    if current_pos < len(content):
        remaining = content[current_pos:].strip("\"").strip("'").strip()
        if remaining:
            result.append(Dialogue(speaker="NARRATOR", text=remaining.rstrip()))
    
    return result
    