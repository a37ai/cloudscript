import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# ------------------------------
# Token Definitions
# ------------------------------

class TokenType(Enum):
    # Basic tokens
    IDENTIFIER = 'IDENTIFIER'
    NUMBER = 'NUMBER'
    STRING = 'STRING'
    
    # Keywords
    FOR = 'for'
    IN = 'in'
    IF = 'if'
    ELSE = 'else'
    SWITCH = 'switch'
    CASE = 'case'
    DEFAULT = 'default'
    TYPE = 'type'
    RESOURCE = 'resource'
    # MODULE = 'module'
    VARIABLE = 'variable'
    OUTPUT = 'output'
    FUNCTION = 'function'
    RETURN = 'return'
    NULL = 'null'
    TRUE = 'true'
    FALSE = 'false'
    MAPS_TO = 'maps_to'
    
    # Operators
    EQUALS = '='
    PLUS = '+'
    MINUS = '-'
    MULTIPLY = '*'
    DIVIDE = '/'
    AND = '&&'
    OR = '||'
    NOT = '!'
    QUESTION = '?'
    COLON = ':'
    PIPE = '|'
    COMMA = ','
    DOT = '.'
    EQUAL_EQUAL = '=='
    NOT_EQUAL = '!='
    GREATER_EQUAL = '>='
    LESS_EQUAL = '<='
    GREATER_THAN = '>'
    LESS_THAN = '<'
    MODULO = '%'
    
    # Delimiters
    LPAREN = '('
    RPAREN = ')'
    LBRACE = '{'
    RBRACE = '}'
    LBRACKET = '['
    RBRACKET = ']'
    
    # Special
    EOF = 'EOF'
    CALC = 'calc'


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
