import { DialogueEntry } from './epubReader';
import { ElevenLabsClient } from 'elevenlabs';

export async function generateAudioForDialogues(dialogues: DialogueEntry[], apiKey: string): Promise<void> {
  if (!apiKey) {
    throw new Error('ElevenLabs API key is required');
  }

  const elevenlabs = new ElevenLabsClient({
    apiKey: apiKey
  });

  const fs = require('fs').promises;
  const outputDir = './audio-output';
  await fs.mkdir(outputDir, { recursive: true });

  for (let i = 0; i < dialogues.length; i++) {
    const { speaker, text } = dialogues[i];
    try {
      // Split long texts into chunks of roughly 200 words
      const chunks = text.split('\n').reduce((acc: string[], line) => {
        const lastChunk = acc[acc.length - 1] || '';
        const words = lastChunk.split(' ').length;
        
        if (words > 200) {
          acc.push(line);
        } else {
          if (acc.length === 0) acc.push(line);
          else acc[acc.length - 1] += '\n' + line;
        }
        return acc;
      }, []);

      for (let j = 0; j < chunks.length; j++) {
        const audio = await elevenlabs.generate({
          voice: "Chris",
          text: chunks[j],
          model_id: "eleven_turbo_v2_5"
        });

        await fs.writeFile(`${outputDir}/${i}-${j}-${speaker}.mp3`, audio);
        console.log(`Generated audio for ${speaker} part ${j+1}/${chunks.length}: ${chunks[j].substring(0, 50)}...`);
      }
    } catch (error) {
      console.error(`Failed to generate audio for ${speaker}:`, error);
    }
  }
}
