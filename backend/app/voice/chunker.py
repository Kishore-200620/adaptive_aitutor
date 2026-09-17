import re

class NarrationStreamer:
    """
    Extracts the NARRATION section from a streaming text block.
    Safely holds back tokens to ensure we don't accidentally speak a section tag like 'BLACKBOARD:'.
    """
    def __init__(self):
        self.buffer = ""
        self.state = "WAIT_NARRATION" # WAIT_NARRATION -> IN_NARRATION -> END_NARRATION
        
    def feed(self, delta: str) -> str:
        if self.state == "END_NARRATION":
            return ""
            
        self.buffer += delta
        new_narration = ""
        
        if self.state == "WAIT_NARRATION":
            if "NARRATION:" in self.buffer:
                self.state = "IN_NARRATION"
                idx = self.buffer.find("NARRATION:") + len("NARRATION:")
                self.buffer = self.buffer[idx:]
            else:
                return ""
                
        if self.state == "IN_NARRATION":
            end_idx = -1
            for tag in ["BLACKBOARD:", "VISUAL_DIRECTIVE:", "QUESTION:"]:
                idx = self.buffer.find(tag)
                if idx != -1:
                    if end_idx == -1 or idx < end_idx:
                        end_idx = idx
                        
            if end_idx != -1:
                self.state = "END_NARRATION"
                new_narration = self.buffer[:end_idx]
                self.buffer = "" 
                return new_narration
            else:
                hold_back = 20 # Hold back characters in case they are forming an end tag like "\n\nBLAC"
                if len(self.buffer) > hold_back:
                    new_narration = self.buffer[:-hold_back]
                    self.buffer = self.buffer[-hold_back:]
                    return new_narration
                return ""
                
        return ""
        
    def flush(self) -> str:
        if self.state == "IN_NARRATION":
            self.state = "END_NARRATION"
            ret = self.buffer
            self.buffer = ""
            return ret
        return ""


class TextChunker:
    """
    Buffers text and yields complete, natural speech chunks (sentences/phrases)
    as soon as a boundary is detected.
    """
    def __init__(self, min_chunk_length=30):
        self.buffer = ""
        self.min_chunk_length = min_chunk_length
        self.abbreviations = {"mr.", "mrs.", "ms.", "dr.", "prof.", "e.g.", "i.e.", "etc.", "vs.", "st.", "inc."}

    def _is_inside_unbreakable_block(self, prefix: str) -> bool:
        """
        Check if the current position (end of prefix) is inside a block that shouldn't be split.
        Checks for markdown code blocks, inline code, and basic LaTeX delimiters.
        """
        # Count code blocks ```
        code_block_count = len(re.findall(r'```', prefix))
        if code_block_count % 2 != 0:
            return True
            
        # Remove code blocks for further checks to avoid false positives
        prefix_no_blocks = re.sub(r'```.*?```', '', prefix, flags=re.DOTALL)
        
        # Count inline code ` (that aren't part of ```)
        inline_code_count = prefix_no_blocks.count('`')
        if inline_code_count % 2 != 0:
            return True
            
        # Check math blocks $$
        math_block_count = len(re.findall(r'\$\$', prefix_no_blocks))
        if math_block_count % 2 != 0:
            return True
            
        # Very basic check for unclosed brackets/parentheses to avoid splitting inside markdown links [text](url)
        # or parentheses (which often contain math or tight clauses).
        open_parens = prefix_no_blocks.count('(') - prefix_no_blocks.count(')')
        open_brackets = prefix_no_blocks.count('[') - prefix_no_blocks.count(']')
        if open_parens > 0 or open_brackets > 0:
            return True
            
        return False

    def feed(self, text: str) -> list[str]:
        self.buffer += text
        chunks = []
        
        while True:
            # Match punctuation followed by whitespace, newline, or end of string.
            matches = list(re.finditer(r'([.!?\:;])(\s+|\n+|$)', self.buffer))
            
            valid_split_idx = -1
            for match in matches:
                split_pos = match.end(1) 
                prefix = self.buffer[:split_pos]
                
                # Check for abbreviation
                words = prefix.split()
                if words and words[-1].lower() in self.abbreviations:
                    continue
                    
                if self._is_inside_unbreakable_block(prefix):
                    continue
                
                # Check minimum length to avoid tiny chunks, unless it's a strong sentence boundary (.!?)
                punct = match.group(1)
                is_strong = punct in ['.', '!', '?']
                
                if len(prefix.strip()) >= self.min_chunk_length or is_strong:
                    valid_split_idx = match.end()
                    break
                
            if valid_split_idx != -1 and valid_split_idx <= len(self.buffer):
                chunk = self.buffer[:valid_split_idx].strip()
                if chunk:
                    chunks.append(chunk)
                self.buffer = self.buffer[valid_split_idx:]
            else:
                break
                
        return chunks

    def flush(self) -> list[str]:
        chunk = self.buffer.strip()
        self.buffer = ""
        return [chunk] if chunk else []
