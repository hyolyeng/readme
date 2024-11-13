import Anthropic from '@anthropic-ai/sdk';
import EPub from 'epub2';

export function cleanText(text: string): string {
  return text.replace(/<[^>]*>/g, '');
}

export async function addSpeakers(text: string): Promise<string> {
  const anthropic = new Anthropic({
    apiKey: process.env.ANTHROPIC_API_KEY,
  });

  const msg = await anthropic.messages.create({
    model: "claude-3-5-sonnet-20241022",
    max_tokens: 2000,
    temperature: 0,
    messages: [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "<examples>\n<example>\n<BOOK_TEXT>\n  The boy across from me was shaking his head from side to side. He'd been doing it for a while, but he'd started speeding up. With a quick jerk he hooked part of his gag on a bit of metal surrounding his neck and pulled it off completely. He showed no satisfaction at that, instead opting to start speaking.\n\n  \"We're allowed to cooperate,\" he shouted. \"We stand a better chance of survival if it's us against them instead of everyone for themselves. We can --\"\n\n  He was drowned out by the airplane opening up its belly. A mile below us were farmlands in the half-light of an overcast day. I struggled against my restraints and prayed that I would wake up, even though I knew in my heart that this wasn't a dream. My feet were dangling into the open sky now.\n</BOOK_TEXT>\n<ideal_output>\n<Boy across>\"We're allowed to cooperate,\"</Boy across>\n<Boy across>\"We stand a better chance of survival if it's us against them instead of everyone for themselves. We can --\"</Boy across>\n</ideal_output>\n</example>\n</examples>\n\n"
          },
          {
            "type": "text",
            "text": `You are an AI assistant tasked with preparing a book's text for audio narration. Your job is to identify and tag dialogue with the speaker's name, allowing for different voices to be used for each character during the audio generation process. Follow these instructions carefully:\n\nHere is the book text that needs to be processed:\n\n<book_text>\n${text}\n</book_text>\n\nYour task is to go through the book text and identify all instances of dialogue, tagging them appropriately. Here's how to proceed:\n\n1. First, analyze the text to identify all characters mentioned. Create a list of these characters in your mind.\n\n2. Carefully read through the text and identify all dialogue.\n\n3. For each piece of dialogue:\n   a. Determine which character is speaking based on the context and your character list.\n   b. Enclose the dialogue in XML tags with the character's name. For example: <Alice>\"Hello, how are you today?\"</Alice>\n   c. If you cannot determine which character is speaking, use <Unknown> as the tag.\n\n4. Omit all non-dialogue text from your output. Only include the tagged dialogue.\n\n5. Ensure that punctuation remains inside the dialogue tags.\n\nHere's an example of the desired output format:\n\n<Alice>\"Good morning, John!\"</Alice>\n<John>\"Morning, Alice. Beautiful day, isn't it?\"</John>\n<Alice>\"It certainly is.\"</Alice>\n<Alice>\"Are you heading to the park?\"</Alice>\n<John>\"Yes, care to join me?\"</John>\n<Newspaper boy>\"Howdy fellas\"</Newspaper boy>\n<Unknown>\"Excuse me, could you tell me the time?\"</Unknown>\n\nRemember, this is just an example. Your actual output should reflect the dialogue found in the provided book text.\n\nBegin processing the text now. When you're finished, enclose your entire output within <tagged_dialogue> tags.`
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
      }
    ]
  });

  return msg.content[0].type === "text" ? msg.content[0].text : "";
}

export interface DialogueEntry {
  speaker: string;
  text: string;
}

export function combineContentAndDialogues(content: string, dialoguesXml: string): DialogueEntry[] {
  const result: DialogueEntry[] = [];
  const dialogueMatches = dialoguesXml.matchAll(/<([^>]+)>"([^"]+)"<\/\1>/gs);
  
  let lastIndex = 0;
  for (const match of dialogueMatches) {
    const [fullMatch, speaker, dialogue] = match;
    const cleanDialogue = dialogue.trim();
    const matchIndex = content.indexOf(cleanDialogue, lastIndex);
    
    // Add any narrative text before this dialogue
    const narrativeText = content.slice(lastIndex, matchIndex).trim();
    if (narrativeText) {
      result.push({ speaker: "NARRATOR", text: narrativeText });
    }
    
    // Add the dialogue
    result.push({ speaker, text: dialogue.trim() });
    lastIndex = matchIndex + cleanDialogue.length;
  }
  
  // Add any remaining narrative text
  const remainingText = content.slice(lastIndex).trim();
  if (remainingText) {
    result.push({ speaker: "NARRATOR", text: remainingText });
  }
  
  return result;
}

export async function saveDialoguesToFile(dialogues: string, outputPath: string): Promise<void> {
  const fs = require('fs').promises;
  await fs.writeFile(outputPath, dialogues, 'utf8');
}

export async function loadDialoguesFromFile(filePath: string): Promise<string> {
  const fs = require('fs').promises;
  return fs.readFile(filePath, 'utf8');
}

export async function readEpubToString(filePath: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const epub = new EPub(filePath);
    let allText = '';
    
    epub.on('end', async () => {
      try {
        const START_CHAPTER = 109
        const END_CHAPTER = 110 // epub.flow.length
        for (let i = START_CHAPTER; i < END_CHAPTER; i++) {
          const chapter = epub.flow[i];
          const text = await new Promise<string>((resolve, reject) => {
            if (chapter.id) {
              epub.getChapter(chapter.id, (error: Error, text?: string) => {
                if (error) reject(error);
                else resolve(text || '');
              });
            }
          });
          allText += text + '\n';
        }
        resolve(allText);
      } catch (error) {
        reject(error);
      }
    });

    epub.parse();
  });
}
