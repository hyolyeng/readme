import unittest
from src.epub_reader import clean_text

class TestEpubReader(unittest.TestCase):
    def test_clean_text_formatting(self):
        # Read input file
        with open('tests/fixtures/in.txt', 'r', encoding='utf-8') as f:
            input_text = f.read()
            
        # Read expected output file
        with open('tests/fixtures/out.txt', 'r', encoding='utf-8') as f:
            expected_output = f.read()
            
        # Clean the input text
        result = clean_text(input_text)
        
        # Compare result with expected output
        self.assertEqual(result.strip(), expected_output.strip())
        
    def test_clean_text_examples(self):
        # Test individual cases
        test_cases = [
            ('<em>italic text</em>', '*italic text*'),
            ('<em class="calibre9">italic with class</em>', '*italic with class*'),
            ('<p>plain and <em>italic</em> mixed</p>', 'plain and *italic* mixed'),
        ]
        
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = clean_text(input_text)
                self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main() 