import os
import json
import ebooklib
from ebooklib import epub
from anthropic import Anthropic
import re

def clean_text(text: str) -> str:
    """
    Clean HTML/XML text to plain text while preserving structure and formatting.
    
    Args:
        text: Input HTML/XML text
        
    Returns:
        Cleaned plain text with preserved formatting
    """
    # Replace horizontal rules
    text = re.sub(r'<hr[^>]*>', '\n---\n', text)
    
    # Convert italics to markdown without adding newlines
    text = re.sub(r'<em[^>]*>\s*(.*?)\s*</em>', r'*\1*', text, flags=re.DOTALL|re.MULTILINE)
    
    # Preserve headings
    text = re.sub(r'<h\d[^>]*>(.*?)</h\d>', r'\1\n\n', text, flags=re.DOTALL)
    
    # Convert paragraphs to double newlines while preserving inline content
    text = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: re.sub(r'\s+', ' ', m.group(1)) + '\n\n', text, flags=re.DOTALL)
    
    # Convert spans to just their content, preserving inline formatting
    text = re.sub(r'<span[^>]*>(.*?)</span>', lambda m: re.sub(r'\s+', ' ', m.group(1)), text, flags=re.DOTALL)
    
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove XML declarations and doctype
    text = re.sub(r'<\?xml[^>]*\?>', '', text)
    text = re.sub(r'<!DOCTYPE[^>]*>', '', text)
    
    # Fix bullet points
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1\n', text, flags=re.DOTALL)
    
    # Clean up whitespace while preserving intentional line breaks
    text = re.sub(r'\s*\n\s*\n\s*', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Clean up lines while preserving paragraph structure
    lines = []
    for line in text.split('\n'):
        cleaned = line.strip()
        if cleaned:
            lines.append(cleaned)
        elif lines and lines[-1] != '':
            lines.append('')
    text = '\n'.join(lines)
    
    # Remove extra whitespace around horizontal rules
    text = re.sub(r'\n\s*---\s*\n', '\n\n---\n\n', text)
    
    # Final cleanup of multiple newlines while preserving paragraphs
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def add_speakers(text: str) -> str:
    """Use Claude to identify speakers and tag dialogue"""
    anthropic = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

    msg = anthropic.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8000,
        temperature=0,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "<examples>\n<example>\n<BOOK_TEXT>\n  The boy across from me was shaking his head from side to side. He'd been doing it for a while, but he'd started speeding up. With a quick jerk he hooked part of his gag on a bit of metal surrounding his neck and pulled it off completely. He showed no satisfaction at that, instead opting to start speaking.\n\n  \"We're allowed to cooperate,\" he shouted. \"We stand a better chance of survival if it's us against them instead of everyone for themselves. We can --\"\n\n  He was drowned out by the airplane opening up its belly. A mile below us were farmlands in the half-light of an overcast day. I struggled against my restraints and prayed that I would wake up, even though I knew in my heart that this wasn't a dream. My feet were dangling into the open sky now.\n</BOOK_TEXT>\n<ideal_output>\n<Boy across>We're allowed to cooperate,</Boy across>\n<Boy across>We stand a better chance of survival if it's us against them instead of everyone for themselves. We can --</Boy across>\n</ideal_output>\n</example>\n</examples>\n\n"
                },
                {
                    "type": "text",
                    "text": f"You are an AI assistant tasked with preparing a book's text for audio narration. Your job is to identify and tag dialogue with the speaker's name, allowing for different voices to be used for each character during the audio generation process. Follow these instructions carefully:\n\nHere is the book text that needs to be processed:\n\n<book_text>\n{text}\n</book_text>\n\nYour task is to go through the book text and identify all instances of dialogue, tagging them appropriately. Here's how to proceed:\n\n1. First, analyze the text to identify all characters mentioned. Create a list of these characters in your mind.\n\n2. Carefully read through the text and identify all dialogue.\n\n3. For each piece of dialogue:\n   a. Determine which character is speaking based on the context and your character list.\n   b. Enclose the dialogue in XML tags with the character's name. For example: <Alice>Hello, how are you today?</Alice>\n   c. If you cannot determine which character is speaking, use <Unknown> as the tag.\n\n4. Omit all non-dialogue text from your output. Only include the tagged dialogue.\n\nHere's an example of the desired output format:\n\n<Alice>Good morning, John!</Alice>\n<John>Morning, Alice. Beautiful day, isn't it?</John>\n<Alice>It certainly is.</Alice>\n<Alice>Are you heading to the park?</Alice>\n<John>Yes, care to join me?</John>\n<Newspaper boy>Howdy fellas</Newspaper boy>\n<Unknown>Excuse me, could you tell me the time?</Unknown>\n\nRemember, this is just an example. Your actual output should reflect the dialogue found in the provided book text.\n\nBegin processing the text now. When you're finished, enclose your entire output within <tagged_dialogue> tags."
                }
            ]
        },
        {
            "role": "assistant",
            "content": [
            {
                "type": "text",
                "text": "<tagged_dialogue>"
            }
            ]
        }]
    )
    
    return msg.content[0].text if msg.content[0].type == "text" else ""

def combine_content_and_dialogues(content: str, dialogues_xml: str) -> list:
    """Combine content and tagged dialogues into a list of entries"""
    import re
    result = []
    dialogue_pattern = r'<([^>]+)>"([^"]+)"</\1>'
    last_index = 0
    
    for match in re.finditer(dialogue_pattern, dialogues_xml):
        speaker, dialogue = match.groups()
        dialogue = dialogue.strip()
        match_index = content.find(dialogue, last_index)
        
        # Add narrative before dialogue
        narrative = content[last_index:match_index].strip()
        if narrative:
            result.append({"speaker": "NARRATOR", "text": narrative})
        
        # Add dialogue
        result.append({"speaker": speaker, "text": dialogue})
        last_index = match_index + len(dialogue)
    
    # Add remaining narrative
    remaining = content[last_index:].strip()
    if remaining:
        result.append({"speaker": "NARRATOR", "text": remaining})
    
    return result

def save_dialogues_to_file(dialogues: str, output_path: str):
    """Save dialogues to a file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(dialogues)

def load_dialogues_from_file(file_path: str) -> str:
    """Load dialogues from a file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def read_epub_to_string(file_path: str) -> str:
    """Read epub file and convert to string"""
    book = epub.read_epub(file_path)
    all_text = []
    
    START_CHAPTER = 109
    END_CHAPTER = 110
    
    for item in list(book.get_items())[START_CHAPTER:END_CHAPTER]:
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            all_text.append(item.get_content().decode('utf-8'))
    
    return '\n'.join(all_text)
