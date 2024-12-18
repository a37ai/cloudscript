from typing import List, Optional
from .tokentypes import Token, TokenType
import codecs


class EnhancedHCLLexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        
        self.keywords = {
            'for': TokenType.FOR,
            'in': TokenType.IN,
            'if': TokenType.IF,
            'else': TokenType.ELSE,
            'switch': TokenType.SWITCH,
            'case': TokenType.CASE,
            'default': TokenType.DEFAULT,
            # 'type': TokenType.TYPE,
            'resource': TokenType.RESOURCE,
            # 'module': TokenType.MODULE,
            'variable': TokenType.VARIABLE,
            'output': TokenType.OUTPUT,
            'function': TokenType.FUNCTION,
            'return': TokenType.RETURN,
            'null': TokenType.NULL,
            # 'bool': 'bool', 
            # 'string': 'string',
            # 'number': 'number',
            # 'Map': 'Map',
            'true': TokenType.TRUE,
            'false': TokenType.FALSE,
            'calc': TokenType.CALC,
            'maps_to': TokenType.MAPS_TO,
        }
        
        self.operators = {
            '==': TokenType.EQUAL_EQUAL,
            '!=': TokenType.NOT_EQUAL,
            '&&': TokenType.AND,
            '||': TokenType.OR,
            '>=': TokenType.GREATER_EQUAL,
            '<=': TokenType.LESS_EQUAL,
            '>': TokenType.GREATER_THAN,
            '<': TokenType.LESS_THAN,
            '=': TokenType.EQUALS,
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '%': TokenType.MODULO,
            '!': TokenType.NOT,
            '?': TokenType.QUESTION,
            ':': TokenType.COLON,
            '|': TokenType.PIPE,
            ',': TokenType.COMMA,
            '.': TokenType.DOT,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
        }
        
    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            char = self.source[self.pos]
            
            # Skip whitespace and handle newlines
            if char.isspace():
                self._handle_whitespace()
                continue
                
            # Handle comments
            if char == '#' or (char == '/' and self.peek() == '/'):
                self._handle_comment()
                continue
            
            # Handle identifiers and keywords
            if char.isalpha() or char == '_':
                self._handle_identifier()
                continue
            
            # Handle numbers
            if char.isdigit():
                self._handle_number()
                continue
            
            # Handle strings
            if char in ['"', "'"]:
                self._handle_string()
                continue
            
            # Handle operators and delimiters
            if any(self.source.startswith(op, self.pos) for op in sorted(self.operators.keys(), key=lambda x: -len(x))):
                self._handle_operator()
                continue
            
            raise SyntaxError(f"Unknown character '{char}' at line {self.line} column {self.column}")
        
        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        return self.tokens
    
    def peek(self, offset=1) -> Optional[str]:
        if self.pos + offset < len(self.source):
            return self.source[self.pos + offset]
        return None
    
    def _handle_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            if self.source[self.pos] == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.pos += 1
    
    def _handle_comment(self):
        if self.source[self.pos] == '#':
            self.pos += 1
            self.column += 1
            while self.pos < len(self.source) and self.source[self.pos] != '\n':
                self.pos += 1
        elif self.source[self.pos:self.pos+2] == '//':
            self.pos += 2
            self.column += 2
            while self.pos < len(self.source) and self.source[self.pos] != '\n':
                self.pos += 1
        # Consume the newline if present
        if self.pos < len(self.source) and self.source[self.pos] == '\n':
            self.line += 1
            self.column = 1
            self.pos += 1
    
    def _handle_identifier(self):
        start_column = self.column
        identifier = ''
        
        while (self.pos < len(self.source) and 
            (self.source[self.pos].isalnum() or self.source[self.pos] in ['_', '$'])):
            identifier += self.source[self.pos]
            self.pos += 1
            self.column += 1
        
        token_type = self.keywords.get(identifier, TokenType.IDENTIFIER)
        self.tokens.append(Token(token_type if isinstance(token_type, TokenType) else TokenType.IDENTIFIER, identifier, self.line, start_column))
        
    def _handle_number(self):
        start_column = self.column
        number_str = ''
        has_dot = False
        
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            if self.source[self.pos] == '.':
                if has_dot:
                    break  # Second dot encountered, stop number
                has_dot = True
            number_str += self.source[self.pos]
            self.pos += 1
            self.column += 1
        
        self.tokens.append(Token(TokenType.NUMBER, number_str, self.line, start_column))
    
    def _handle_string(self):
        quote_char = self.source[self.pos]
        self.pos += 1
        self.column += 1
        start_column = self.column
        string_value = ''
        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == '\\':
                self.pos += 1
                self.column += 1
                if self.pos < len(self.source):
                    escape_char = self.source[self.pos]
                    if escape_char in 'nrt\\\'"':
                        escape_sequence = '\\' + escape_char
                        string_value += codecs.decode(escape_sequence, 'unicode_escape')
                        self.pos += 1
                        self.column += 1
                    else:
                        string_value += escape_char
                        self.pos += 1
                        self.column += 1
                else:
                    string_value += '\\'
            elif char == quote_char:
                self.pos += 1
                self.column += 1
                break
            else:
                string_value += char
                self.pos += 1
                self.column += 1
        else:
            raise SyntaxError(f"Unterminated string starting at line {self.line} column {start_column}")
        self.tokens.append(Token(TokenType.STRING, string_value, self.line, start_column))
    
    def _handle_operator(self):
        start_column = self.column
        # Sort operators by length in descending order to match multi-character operators first
        for op in sorted(self.operators.keys(), key=lambda x: -len(x)):
            op_length = len(op)
            if self.source.startswith(op, self.pos):
                token_type = self.operators[op]
                self.tokens.append(Token(token_type, op, self.line, start_column))
                self.pos += op_length
                self.column += op_length
                return
        # If no operator matched, raise error
        unknown_char = self.source[self.pos]
        raise SyntaxError(f"Unknown operator '{unknown_char}' at line {self.line} column {self.column}")