import { cleanText, combineContentAndDialogues } from './epubReader';

import { readFileSync } from 'fs';

// Read test files
const content = readFileSync('epub_in.txt', 'utf8');
const dialoguesXml = readFileSync('test_dialogues.xml', 'utf8');

// Remove chapter end notes
const contentWithoutNotes = content.split('Chapter End Notes')[0];
const justContent = cleanText(contentWithoutNotes);

// Run the combination
const result = combineContentAndDialogues(justContent, dialoguesXml);

// Print results
console.log('Combined results:');
result.forEach((entry, i) => {
  console.log(`\n[${i}] Speaker: ${entry.speaker}`);
  console.log(`Text: ${entry.text}`);
});
