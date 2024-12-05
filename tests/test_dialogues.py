import unittest
import json
from src.tag_dialogues import split_content_by_speaker

class TestDialogues(unittest.TestCase):
    def test_split_content_by_speaker(self):
        # Read and normalize input files
        with open('tests/fixtures/chunk_in.txt', 'r', encoding='utf-8') as f:
            content = f.read().replace('"', "'").replace('"', "'")
            
        with open('tests/fixtures/dialogues.json', 'r', encoding='utf-8') as f:
            dialogues = json.load(f)
            
        with open('tests/fixtures/expected.json', 'r', encoding='utf-8') as f:
            expected = json.load(f)
            
        # Run the function
        result = split_content_by_speaker(content, dialogues)

        with open("test-output.json", 'w') as f:
            json.dump(result, f)
        
        # Normalize quotes in both result and expected output
        def normalize_quotes(data):
            return [{
                "speaker": item["speaker"],
                "text": item["text"].replace('"', "'").replace('"', "'")
            } for item in data]
            
        # Set maxDiff to None to see full diff
        self.maxDiff = None
        
        # Compare with expected output 
        norm_result = normalize_quotes(result)
        norm_expected = normalize_quotes(expected)
        
        # Print exact content for debugging
        print("\nResult:")
        print(repr(norm_result[0]["text"]))
        print("\nExpected:")
        print(repr(norm_expected[0]["text"]))
        
        self.assertEqual(norm_result, norm_expected)

if __name__ == '__main__':
    unittest.main()
