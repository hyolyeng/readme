import { addSpeakers, cleanText, combineContentAndDialogues, loadDialoguesFromFile, readEpubToString, saveDialoguesToFile } from './epubReader';

import { generateAudioForDialogues } from './audio';

async function main() {
  const filePath = process.argv[2];
  if (!filePath) {
    console.error('Please provide an epub file path');
    process.exit(1);
  }

  try {
    const content = await readEpubToString(filePath);

    // Remove chapter end notes
    const contentWithoutNotes = content.split('Chapter End Notes')[0];
    const justContent = cleanText(contentWithoutNotes);

    const combinedPath = 'cached-combined.json';
    let combined;
    try {
      combined = JSON.parse(await loadDialoguesFromFile(combinedPath));
    } catch {
      const dialoguesPath = 'cached-dialogues.xml';
      let dialogues;
      try {
        dialogues = await loadDialoguesFromFile(dialoguesPath);
      } catch {
        dialogues = await addSpeakers(justContent);
        await saveDialoguesToFile(dialogues, dialoguesPath);
      }
      combined = combineContentAndDialogues(justContent, dialogues);
      await saveDialoguesToFile(JSON.stringify(combined), combinedPath);
    }

    // Generate audio if API key is provided
    const elevenLabsApiKey = process.env.ELEVENLABS_API_KEY;
    if (elevenLabsApiKey) {
      await generateAudioForDialogues(combined, elevenLabsApiKey);
    }
  } catch (error) {
    console.error('Error reading epub:', error);
  }
}

main();
