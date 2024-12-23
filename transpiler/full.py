import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum
from abc import ABC, abstractmethod
import pprint
import hcl2
import codecs


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

# ------------------------------
# AST Node Definitions
# ------------------------------

class ASTNode(ABC):
    @abstractmethod
    def accept(self, visitor: 'ASTVisitor') -> Any:
        pass

@dataclass
class KeyValueNode(ASTNode):
    key: str
    value: ASTNode

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_key_value(self)

@dataclass
class BlockNode(ASTNode):
    statements: List[ASTNode]
    
    def accept(self, visitor: 'ASTVisitor', include_braces: bool = True) -> Any:
        return visitor.visit_block(self, include_braces)

@dataclass
class TypeInstanceNode(ASTNode):
    label: str
    type_name: str
    block: BlockNode

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_type_instance(self)

@dataclass
class TernaryExpressionNode(ASTNode):
    condition: ASTNode
    true_expr: ASTNode
    false_expr: ASTNode

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_ternary_expression(self)

@dataclass
class ResourceNode(ASTNode):
    type: str
    name: str
    block: BlockNode
    type_instance: Optional[str] = None  # Add this field
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_resource(self)

@dataclass
class ForLoopNode(ASTNode):
    iterator: str
    iterable: ASTNode
    body: BlockNode
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_for_loop(self)

@dataclass
class IfNode(ASTNode):
    condition: ASTNode
    then_block: BlockNode
    else_block: Optional[BlockNode]
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_if(self)

@dataclass
class SwitchNode(ASTNode):
    value: ASTNode
    cases: List[Tuple[ASTNode, BlockNode]]
    default: Optional[BlockNode]
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_switch(self)

@dataclass
class FunctionNode(ASTNode):
    name: str
    params: List['Variable']
    return_type: Optional['CustomType']
    body: BlockNode
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_function(self)

@dataclass
class VariableAssignmentNode(ASTNode):
    name: str
    value: ASTNode
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_variable_assignment(self)

@dataclass
class ExpressionNode(ASTNode):
    left: ASTNode
    operator: Optional[Token]
    right: Optional[ASTNode]
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_expression(self)

@dataclass
class ReturnNode(ASTNode):
    value: ASTNode
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_return(self)

@dataclass
class RangeNode(ASTNode):
    function_name: str
    arguments: List[ASTNode]
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_range(self)

@dataclass
class LiteralNode(ASTNode):
    value: Any
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_literal(self)

@dataclass
class IdentifierNode(ASTNode):
    name: str
    
    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_identifier(self)

@dataclass
class FunctionCallNode(ASTNode):
    function: ASTNode
    arguments: List[ASTNode]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_function_call(self)

@dataclass
class AttributeAccessNode(ASTNode):
    object: ASTNode
    attribute: str

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_attribute_access(self)

@dataclass
class ListNode(ASTNode):
    elements: List[ASTNode]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_list(self)

@dataclass
class ObjectNode(ASTNode):
    attributes: Dict[str, ASTNode]

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_object(self)

@dataclass
class NamedBlockNode(ASTNode):
    name: str
    label: Optional[str]
    block: BlockNode

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_named_block(self)

# ------------------------------
# Type Definitions
# ------------------------------

@dataclass
class CustomType:
    name: str
    constraints: Optional[Dict[str, 'CustomType']] = None
    union_types: Optional[List['CustomType']] = None
    is_nullable: bool = False

@dataclass
class ASTFieldDefinition:
    name: str
    type: CustomType
    default_value: Optional[ASTNode] = None

@dataclass
class TypeDefNode(ASTNode):
    name: str
    fields: List[ASTFieldDefinition]
    base_type: Optional[str] = None

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_type_def(self)

@dataclass
class Variable:
    name: str
    type: CustomType
    value: Any = None

@dataclass
class Scope:
    variables: Dict[str, Variable] = field(default_factory=dict)
    parent: Optional['Scope'] = None
    
    def get(self, name: str) -> Optional[Variable]:
        if name in self.variables:
            return self.variables[name]
        if self.parent:
            return self.parent.get(name)
        return None
        
    def set(self, name: str, variable: Variable):
        self.variables[name] = variable

@dataclass
class BlockExpressionNode(ASTNode):
    expression: ASTNode
    block: BlockNode

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_block_expression(self)

@dataclass
class RawBlockNode(ASTNode):
    name: str
    label: Optional[str]
    content: str

    def accept(self, visitor: 'ASTVisitor'):
        return visitor.visit_raw_block(self)

@dataclass
class MapsToNode(ASTNode):
    source: ASTNode
    target: ASTNode

    def accept(self, visitor: 'ASTVisitor') -> Any:
        return visitor.visit_maps_to(self)

# ------------------------------
# AST Visitor Interface
# ------------------------------

class ASTVisitor(ABC):
    @abstractmethod
    def visit_key_value(self, node: KeyValueNode) -> Any:
        pass
    @abstractmethod
    def visit_block(self, node: BlockNode) -> Any:
        pass
    
    @abstractmethod
    def visit_resource(self, node: ResourceNode) -> Any:
        pass
    
    @abstractmethod
    def visit_for_loop(self, node: ForLoopNode) -> Any:
        pass
    
    @abstractmethod
    def visit_if(self, node: IfNode) -> Any:
        pass
    
    @abstractmethod
    def visit_switch(self, node: SwitchNode) -> Any:
        pass
    
    @abstractmethod
    def visit_function(self, node: FunctionNode) -> Any:
        pass
    
    @abstractmethod
    def visit_type_def(self, node: TypeDefNode) -> Any:
        pass
    
    @abstractmethod
    def visit_variable_assignment(self, node: VariableAssignmentNode) -> Any:
        pass
    
    @abstractmethod
    def visit_expression(self, node: ExpressionNode) -> Any:
        pass
    
    @abstractmethod
    def visit_return(self, node: ReturnNode) -> Any:
        pass
    
    @abstractmethod
    def visit_range(self, node: RangeNode) -> Any:
        pass
    
    @abstractmethod
    def visit_literal(self, node: LiteralNode) -> Any:
        pass
    
    @abstractmethod
    def visit_identifier(self, node: IdentifierNode) -> Any:
        pass
    
    @abstractmethod
    def visit_function_call(self, node: FunctionCallNode) -> Any:
        pass
    
    @abstractmethod
    def visit_attribute_access(self, node: AttributeAccessNode) -> Any:
        pass
    
    @abstractmethod
    def visit_list(self, node: ListNode) -> Any:
        pass
    
    @abstractmethod
    def visit_object(self, node: ObjectNode) -> Any:
        pass

    @abstractmethod
    def visit_named_block(self, node: NamedBlockNode) -> Any:
        pass

    @abstractmethod
    def visit_ternary_expression(self, node: TernaryExpressionNode) -> Any:
        pass

    @abstractmethod
    def visit_type_instance(self, node: TypeInstanceNode) -> Any:
        pass


# ------------------------------
# Type System Core
# ------------------------------

@dataclass
class CalculatedField:
    expression: ASTNode  # Changed from str to ASTNode
    dependencies: List[str]  # List of field names this computation depends on

    def calculate(self, values: Dict[str, Any], evaluator) -> Any:
        # Evaluate the expression using evaluator
        return evaluator(self.expression, values)

@dataclass
class TypeConstraint:
    """Represents a constraint on a type"""
    value_type: Union[CustomType, List[str]]  # Updated to accept Type objects
    nullable: bool = False

    def validate(self, value: Any, type_registry: 'TypeRegistry') -> Optional[str]:
        if value is None:
            if self.nullable:
                return None
            return "Value cannot be null"

        if isinstance(self.value_type, list):
            if value not in self.value_type:
                return f"Value must be one of: {', '.join(map(str, self.value_type))}"
        elif isinstance(self.value_type, CustomType):
            # Handle custom types and built-in types
            if self.value_type.union_types:
                for union_type in self.value_type.union_types:
                    if type_registry.validate_value_against_type(value, union_type):
                        return None
                return f"Value does not match any of the union types: {', '.join([t.name for t in self.value_type.union_types])}"
            else:
                if not type_registry.validate_value_against_type(value, self.value_type):
                    return f"Value does not match type: {self.value_type.name}"
        else:
            # Handle built-in types like 'string', 'number', etc.
            if not isinstance(value, self._get_python_type(self.value_type.name)):
                return f"Value must be of type {self.value_type.name}"
        return None

    def _get_python_type(self, type_name: str):
        type_mapping = {
            'string': str,
            'number': (int, float),
            'bool': bool,
            'any': object
        }
        return type_mapping.get(type_name, object)

@dataclass
class FieldDefinition:
    name: str
    constraint: TypeConstraint
    default_value: Optional[Any] = None
    calculated: Optional[CalculatedField] = None
    description: Optional[str] = None

@dataclass
class TypeDefinition:
    """Represents a complete type definition"""
    name: str
    fields: Dict[str, FieldDefinition]
    base_type: Optional[str] = None
    description: Optional[str] = None

class TypeRegistry:
    """Manages type definitions and handles inheritance"""
    def __init__(self):
        self.types: Dict[str, TypeDefinition] = {}
        
    def register_type(self, type_def: TypeDefinition):
        """Register a new type definition"""
        if type_def.base_type and type_def.base_type not in self.types:
            raise ValueError(f"Base type {type_def.base_type} not found")
        self.types[type_def.name] = type_def

    def validate_value_against_type(self, value: Any, type_def: CustomType) -> bool:
        if type_def.name in ['string', 'number', 'bool', 'any']:
            python_type = self._get_python_type(type_def.name)
            return isinstance(value, python_type)
        elif type_def.name in self.types:
            # Custom type validation
            errors = self.validate_instance(type_def.name, value)
            return not errors
        else:
            # Treat it as a string literal
            if isinstance(value, str) and value == type_def.name:
                return True
            return False

    def _get_python_type(self, type_name: str):
        type_mapping = {
            'string': str,
            'number': (int, float),
            'bool': bool,
            'any': object
        }
        return type_mapping.get(type_name, object)
        
    def get_all_fields(self, type_name: str) -> Dict[str, FieldDefinition]:
        """Get all fields for a type, including inherited ones"""
        if type_name not in self.types:
            raise ValueError(f"Type {type_name} not found")
            
        type_def = self.types[type_name]
        fields = {}
        
        # Get base type fields first
        if type_def.base_type:
            fields.update(self.get_all_fields(type_def.base_type))
            
        # Add/override with this type's fields
        fields.update(type_def.fields)
        return fields
        
    def validate_instance(self, type_name: str, values: Dict[str, Any]) -> List[str]:
        """Validate values against a type definition"""
        if type_name not in self.types:
            return [f"Unknown type: {type_name}"]

        errors = []
        fields = self.get_all_fields(type_name)

        # Check required fields
        for name, field in fields.items():
            if name not in values:
                if field.default_value is None and field.calculated is None:
                    errors.append(f"Missing required field: {name}")
                continue

            if error := field.constraint.validate(values[name], self):
                errors.append(f"Field {name}: {error}")

        return errors
            
    def apply_defaults(self, type_name: str, values: Dict[str, Any], evaluator=None) -> Dict[str, Any]:
        """Apply default values for missing fields"""

        if evaluator is None:
            raise ValueError("Evaluator function must be provided to apply_defaults.")
       
        if type_name not in self.types:
            raise ValueError(f"Type {type_name} not found")
            
        result = dict(values)
        fields = self.get_all_fields(type_name)
        
        # First pass: Apply non-calc defaults
        for name, field in fields.items():
            if name not in result and field.default_value is not None:
                if isinstance(field.default_value, ASTNode):
                    result[name] = evaluator(field.default_value, result)
                else:
                    result[name] = field.default_value
                    
        # Second pass: Apply calc values
        for name, field in fields.items():
            if field.calculated is not None:
                # Pass the current values dict to calculate
                result[name] = field.calculated.calculate(result, evaluator)
                
        return result

# ------------------------------
# AST Transformer for expanding types wherever they occur
# ------------------------------

class ASTTransformer:
    def __init__(self, type_registry: TypeRegistry):
        self.type_registry = type_registry

    def transform(self, node: ASTNode) -> ASTNode:
        method_name = f'transform_{type(node).__name__}'
        transform_method = getattr(self, method_name, self.generic_transform)
        return transform_method(node)

    def generic_transform(self, node: ASTNode) -> ASTNode:
        return node
    
    def transform_ObjectNode(self, node: ObjectNode) -> ASTNode:
        # Check for custom type
        if 'type' in node.attributes:
            type_attr = node.attributes['type']
            if isinstance(type_attr, IdentifierNode):
                type_name = type_attr.name
            elif isinstance(type_attr, LiteralNode):
                type_name = type_attr.value
            else:
                raise ValueError(f"Unsupported type value: {type_attr}")

            # Check if the type_name exists in the TypeRegistry
            if type_name in self.type_registry.types:
                # Collect attribute values
                values = {}
                for key, value_node in node.attributes.items():
                    if key != 'type':
                        # Transform value node recursively
                        transformed_value = self.transform(value_node)
                        # Convert transformed node to value
                        value = self.node_to_value(transformed_value)
                        values[key] = value

                # Apply type defaults and calculated fields
                complete_values = self.type_registry.apply_defaults(
                    type_name,
                    values,
                    evaluator=lambda expr, vars=values: self.evaluate_expression(expr, vars)
                )

                # Remove 'type' field
                complete_values.pop('type', None)

                # Convert complete values back to AST nodes
                new_attributes = {k: self.value_to_node(v) for k, v in complete_values.items()}

                # Transform nested nodes in the new attributes
                for key in new_attributes:
                    new_attributes[key] = self.transform(new_attributes[key])

                return ObjectNode(new_attributes)
            else:
                # 'type' field does not reference a defined type; treat it as a regular field
                new_attributes = {}
                for key, value_node in node.attributes.items():
                    new_attributes[key] = self.transform(value_node)
                return ObjectNode(new_attributes)
        else:
            # No 'type' field; treat as a regular object
            new_attributes = {}
            for key, value_node in node.attributes.items():
                new_attributes[key] = self.transform(value_node)
            return ObjectNode(new_attributes)

    def transform_ListNode(self, node: ListNode) -> ASTNode:
        new_elements = [self.transform(element) for element in node.elements]
        return ListNode(new_elements)

    def transform_BlockNode(self, node: BlockNode) -> ASTNode:
        # First, transform all statements
        new_statements = [self.transform(stmt) for stmt in node.statements]

        # Check if all statements are KeyValueNodes
        if all(isinstance(stmt, KeyValueNode) for stmt in new_statements):
            # Collect key-value pairs
            attributes = {stmt.key: stmt.value for stmt in new_statements}
            # Check if 'type' is in attributes
            if 'type' in attributes:
                # Create an ObjectNode
                obj_node = ObjectNode(attributes)
                # Transform the ObjectNode (type expansion)
                transformed_obj_node = self.transform_ObjectNode(obj_node)
                # Convert back to KeyValueNodes
                transformed_statements = [KeyValueNode(k, v) for k, v in transformed_obj_node.attributes.items()]
                return BlockNode(transformed_statements)
        # If not, return block with transformed statements
        return BlockNode(new_statements)
    
    def node_to_value(self, node: ASTNode) -> Any:
        if isinstance(node, LiteralNode):
            return node.value
        elif isinstance(node, ObjectNode):
            return {k: self.node_to_value(v) for k, v in node.attributes.items()}
        elif isinstance(node, ListNode):
            return [self.node_to_value(elem) for elem in node.elements]
        elif isinstance(node, IdentifierNode):
            return node.name
        else:
            raise NotImplementedError(f"Cannot convert node type {type(node)} to value")

    def value_to_node(self, value: Any) -> ASTNode:
        if isinstance(value, dict):
            attributes = {k: self.value_to_node(v) for k, v in value.items()}
            return ObjectNode(attributes)
        elif isinstance(value, list):
            elements = [self.value_to_node(elem) for elem in value]
            return ListNode(elements)
        elif isinstance(value, str):
            return LiteralNode(value)
        elif isinstance(value, (int, float, bool)):
            return LiteralNode(value)
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")
        
    def evaluate_expression(self, node: ASTNode, variables=None) -> Any:
        if variables is None:
            variables = {}
        
        if isinstance(node, LiteralNode):
            if isinstance(node.value, str):
                # Handle interpolated strings like "${var1}.${var2}"
                def replace_match(match):
                    var_name = match.group(1)
                    return str(variables.get(var_name, ''))
                
                interpolated = re.sub(r'\$\{(\w+)\}', replace_match, node.value)
                return interpolated
            else:
                return node.value
        
        elif isinstance(node, IdentifierNode):
            return variables.get(node.name, node.name)
        
        elif isinstance(node, ListNode):
            # Recursively evaluate each element in the list
            return [self.evaluate_expression(element, variables) for element in node.elements]
        
        elif isinstance(node, ObjectNode):
            # Recursively evaluate each attribute in the object
            return {key: self.evaluate_expression(value, variables) for key, value in node.attributes.items()}
        
        elif isinstance(node, ExpressionNode):
            left = self.evaluate_expression(node.left, variables)
            right = self.evaluate_expression(node.right, variables) if node.right else None
            op = node.operator.value if node.operator else None
            if op == '+':
                return left + right
            elif op == '.':
                return f"{left}.{right}"
            elif op == '==':
                return left == right
            elif op == '!=':
                return left != right
            elif op == '>':
                return left > right
            elif op == '>=':
                return left >= right
            elif op == '<':
                return left < right
            elif op == '<=':
                return left <= right
            elif op == '&&':
                return left and right
            elif op == '||':
                return left or right
            else:
                raise NotImplementedError(f"Operator {op} not implemented in evaluator.")
        
        elif isinstance(node, TernaryExpressionNode):
            condition = self.evaluate_expression(node.condition, variables)
            if condition:
                return self.evaluate_expression(node.true_expr, variables)
            else:
                return self.evaluate_expression(node.false_expr, variables)
        
        elif isinstance(node, AttributeAccessNode):
            obj = self.evaluate_expression(node.object, variables)
            return f"{obj}.{node.attribute}"
        
        elif isinstance(node, FunctionCallNode):
            # Handle function calls if necessary
            raise NotImplementedError("Function calls are not supported in the evaluator.")
        
        else:
            raise NotImplementedError(f"Cannot evaluate node type {type(node)}")
        
    def transform_NamedBlockNode(self, node: NamedBlockNode) -> ASTNode:
        # Transform the block
        transformed_block = self.transform(node.block)

        # Check if the block contains a single ObjectNode due to extra braces
        if (len(transformed_block.statements) == 1 and
            isinstance(transformed_block.statements[0], ObjectNode)):
            inner_object = transformed_block.statements[0]
            # Transform the inner ObjectNode
            transformed_object = self.transform(inner_object)
            # Replace the block's statements with the transformed object's attributes as KeyValueNodes
            new_statements = [
                KeyValueNode(key, value)
                for key, value in transformed_object.attributes.items()
            ]
            transformed_block = BlockNode(new_statements)
        
        return NamedBlockNode(name=node.name, label=node.label, block=transformed_block)
    
    def transform_KeyValueNode(self, node: KeyValueNode) -> ASTNode:
        transformed_value = self.transform(node.value)
        return KeyValueNode(key=node.key, value=transformed_value)

# ------------------------------
# Lexer Implementation
# ------------------------------

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

# ------------------------------
# Parser Implementation
# ------------------------------

class EnhancedHCLParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.current_scope = Scope()
        self.type_registry = TypeRegistry()
        self.block_level = 0

        self.operator_token_types = {
            TokenType.OR,
            TokenType.AND,
            TokenType.EQUAL_EQUAL,
            TokenType.NOT_EQUAL,
            TokenType.GREATER_THAN,
            TokenType.GREATER_EQUAL,
            TokenType.LESS_THAN,
            TokenType.LESS_EQUAL,
            TokenType.PLUS,
            TokenType.MINUS,
            TokenType.MULTIPLY,
            TokenType.DIVIDE,
            TokenType.MODULO,
        }
    
    @property
    def current_token(self) -> Token:
        return self.tokens[self.pos]
    
    def consume(self, token_type: TokenType) -> Token:
        if self.match(token_type):
            token = self.tokens[self.pos]
            self.pos += 1
            return token
        else:
            current = self.current_token
            raise SyntaxError(f"Expected token {token_type} at line {current.line} column {current.column}, got {current.type}")
    
    def match(self, token_type: TokenType) -> bool:
        if self.current_token.type == token_type:
            return True
        return False
    
    def parse(self) -> BlockNode:
        statements = []
        while not self.match(TokenType.EOF):
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return BlockNode(statements)
    
    def parse_statement(self) -> Optional[ASTNode]:
        if not self.current_token:
            return None
        token = self.current_token
        if token.type == TokenType.RETURN:
            return self.parse_return_statement()
        elif token.type == TokenType.RESOURCE:
            return self.parse_resource()
        elif token.type == TokenType.FOR:
            return self.parse_for_loop()
        elif token.type == TokenType.IF:
            return self.parse_if_statement()
        elif token.type == TokenType.SWITCH:
            return self.parse_switch_statement()
        elif token.type == TokenType.FUNCTION:
            return self.parse_function()
        elif token.type == TokenType.IDENTIFIER and token.value == 'type' and self.block_level == 0:
            return self.parse_type_definition()
        elif token.type == TokenType.IDENTIFIER and token.value == "service":
            return self.parse_service_block()
        elif token.type in (TokenType.IDENTIFIER, TokenType.STRING):
            if self.peek() and self.peek().type == TokenType.MAPS_TO:
                return self.parse_maps_to_statement()
            elif self.peek() and self.peek().type == TokenType.EQUALS:
                return self.parse_variable_assignment()
            elif self.peek() and self.peek().type == TokenType.LBRACE:
                return self.parse_named_block()
            else:
                return self.parse_expression_statement()
        else:
            expr = self.parse_expression()
            if expr:
                return ExpressionNode(expr, None, None)
            return None
        
    def parse_maps_to_statement(self) -> MapsToNode:
        source_token = self.consume(self.current_token.type) 
        source_node = LiteralNode(source_token.value)
        self.consume(TokenType.MAPS_TO)
        target_node = self.parse_expression()
        return MapsToNode(source=source_node, target=target_node)
        
    def parse_return_statement(self) -> ReturnNode:
        self.consume(TokenType.RETURN)
        value = self.parse_expression()
        return ReturnNode(value)
    
    def parse_resource(self) -> ResourceNode:
        self.consume(TokenType.RESOURCE)
        type_token = self.consume(TokenType.STRING)
        name_token = self.consume(TokenType.STRING)
        
        # Parse the block first
        block = self.parse_block()
        
        # Look for type field in the block
        type_instance = None
        for stmt in block.statements:
            if isinstance(stmt, KeyValueNode) and stmt.key == 'type':
                if isinstance(stmt.value, IdentifierNode):
                    type_instance = stmt.value.name
                    break
                elif isinstance(stmt.value, LiteralNode):
                    type_instance = stmt.value.value
                    break
        
        # If type is specified, validate and apply defaults
        if type_instance:
            values = self._block_to_values(block)
            errors = self.type_registry.validate_instance(type_instance, values)
            if errors:
                line = type_token.line
                raise TypeError(f"At line {line}: " + "\n".join(errors))
                
            # complete_values = self.type_registry.apply_defaults(type_instance, values)
            # block = self._values_to_block(complete_values)
        
        return ResourceNode(
            type=type_token.value,
            name=name_token.value,
            block=block,
            type_instance=type_instance
        )
    
    def parse_service_block(self) -> NamedBlockNode:
        """Parse service block with proper handling of name and block"""
        self.consume(TokenType.IDENTIFIER)  # Consume 'service'
        name_token = self.consume(TokenType.STRING)
        block = self.parse_block()
        return NamedBlockNode(name="service", label=name_token.value, block=block)
        
    def _block_to_values(self, block: BlockNode) -> Dict[str, Any]:
        values = {}
        for stmt in block.statements:
            if isinstance(stmt, KeyValueNode):
                if isinstance(stmt.value, LiteralNode):
                    values[stmt.key] = stmt.value.value
                elif isinstance(stmt.value, IdentifierNode):
                    values[stmt.key] = stmt.value.name
        return values

    def _values_to_block(self, values: Dict[str, Any]) -> BlockNode:
        statements = []
        for key, value in values.items():
            value_node = self._value_to_node(value)
            statements.append(KeyValueNode(
                key=key,
                value=value_node
            ))
        return BlockNode(statements)
    
    def parse_for_loop(self) -> ForLoopNode:
        """Enhanced for loop parser with proper token handling"""
        self.consume(TokenType.FOR)
        
        if not self.match(TokenType.IDENTIFIER):
            raise SyntaxError(f"Expected identifier after 'for' at line {self.current_token.line}")
            
        iterator = self.consume(TokenType.IDENTIFIER).value
        
        if not self.match(TokenType.IN):
            raise SyntaxError(f"Expected 'in' after iterator at line {self.current_token.line}")
            
        self.consume(TokenType.IN)
        iterable = self.parse_expression()
        
        if not self.match(TokenType.LBRACE):
            raise SyntaxError(f"Expected '{{' after for loop header at line {self.current_token.line}")
            
        body = self.parse_block()
        return ForLoopNode(iterator, iterable, body)
    
    def parse_if_statement(self) -> IfNode:
        self.consume(TokenType.IF)
        condition = self.parse_expression()
        then_block = self.parse_block()
        else_block = None
        if self.match(TokenType.ELSE):
            self.consume(TokenType.ELSE)
            else_block = self.parse_block()
        return IfNode(condition, then_block, else_block)
    
    def parse_switch_statement(self) -> SwitchNode:
        """Enhanced switch statement parser with proper token handling"""
        self.consume(TokenType.SWITCH)
        value = self.parse_expression()
        cases = []
        default = None
        
        self.consume(TokenType.LBRACE)
        while not self.match(TokenType.RBRACE):
            if self.match(TokenType.CASE):
                self.consume(TokenType.CASE)
                case_value = self.parse_expression()
                case_block = self.parse_block()
                cases.append((case_value, case_block))
            elif self.match(TokenType.DEFAULT):
                self.consume(TokenType.DEFAULT)
                default = self.parse_block()
            else:
                raise SyntaxError(f"Expected 'case' or 'default' in switch statement at line {self.current_token.line}")
                
        self.consume(TokenType.RBRACE)
        return SwitchNode(value, cases, default)
    
    def parse_function(self) -> FunctionNode:
        self.consume(TokenType.FUNCTION)
        name_token = self.consume(TokenType.IDENTIFIER)
        self.consume(TokenType.LPAREN)
        params = self.parse_parameter_list()
        self.consume(TokenType.RPAREN)
        return_type = None
        if self.match(TokenType.COLON):
            self.consume(TokenType.COLON)
            return_type = self.parse_type_annotation()
        body = self.parse_block()
        return FunctionNode(name_token.value, params, return_type, body)
    
    def parse_type_definition(self) -> TypeDefNode:
        if self.current_token.type == TokenType.IDENTIFIER and self.current_token.value == 'type':
            self.consume(TokenType.IDENTIFIER)  # Consume 'type'
            name_token = self.consume(TokenType.IDENTIFIER)
            base_type = None
            fields = {}
            ast_fields = []
            self.consume(TokenType.LBRACE)

            while True:
                if self.match(TokenType.RBRACE):
                    break
                elif self.match(TokenType.IDENTIFIER):
                    field_name = self.consume(TokenType.IDENTIFIER).value

                    if field_name == 'base':
                        self.consume(TokenType.COLON)
                        base_type = self.consume(TokenType.IDENTIFIER).value
                        # Consume optional comma after base field
                        if self.match(TokenType.COMMA):
                            self.consume(TokenType.COMMA)
                    else:
                        self.consume(TokenType.COLON)
                        field_type = self.parse_type_annotation()
                        default_value = None
                        calculated = None

                        if self.match(TokenType.EQUALS):
                            self.consume(TokenType.EQUALS)
                            if self.match(TokenType.CALC):
                                self.consume(TokenType.CALC)
                                self.consume(TokenType.LBRACE)
                                expression = self.parse_expression()
                                self.consume(TokenType.RBRACE)
                                calculated = CalculatedField(expression, dependencies=[])  # dependencies can be handled as needed
                            else:
                                default_value = self.parse_expression()

                        # Create FieldDefinition for TypeRegistry
                        fields[field_name] = FieldDefinition(
                            name=field_name,
                            constraint=TypeConstraint(value_type=field_type),
                            default_value=default_value,
                            calculated=calculated
                        )

                        # Create ASTFieldDefinition for AST
                        ast_fields.append(ASTFieldDefinition(
                            name=field_name,
                            type=field_type,
                            default_value=default_value
                        ))

                        # Optional comma
                        if self.match(TokenType.COMMA):
                            self.consume(TokenType.COMMA)
                else:
                    # Consume the unexpected token to prevent infinite loop
                    unexpected_token = self.current_token
                    self.consume(unexpected_token.type)
                    raise SyntaxError(f"Expected field name in type definition at line {unexpected_token.line}")

            self.consume(TokenType.RBRACE)

            # Register the type definition
            type_def = TypeDefinition(
                name=name_token.value,
                fields=fields,
                base_type=base_type
            )
            self.type_registry.register_type(type_def)

            # Return the AST node
            return TypeDefNode(name=name_token.value, fields=ast_fields, base_type=base_type)
        else:
            # Consume the unexpected token to prevent infinite loop
            unexpected_token = self.current_token
            self.consume(unexpected_token.type)
            raise SyntaxError(f"Expected 'type' keyword at line {unexpected_token.line}")
    
    def parse_variable_assignment(self) -> VariableAssignmentNode:
        name_token = self.consume(TokenType.IDENTIFIER)
        self.consume(TokenType.EQUALS)
        value = self.parse_expression()
        return VariableAssignmentNode(name_token.value, value)
    
    def parse_expression_statement(self) -> ExpressionNode:
        expr = self.parse_expression()
        return ExpressionNode(expr, None, None)
    
    def parse_expression(self, precedence=0) -> ASTNode:
        left = self.parse_primary()
        if left is None:
            raise SyntaxError(f"Invalid expression at line {self.current_token.line}")

        while True:
            current = self.current_token
            current_precedence = self.get_precedence(current.type)

            if current_precedence < precedence:
                break

            if current.type in self.operator_token_types:
                op = self.consume(current.type)
                right = self.parse_expression(current_precedence + 1)
                left = ExpressionNode(left, op, right)
            elif current.type == TokenType.LBRACE:
                # Handle nested blocks within expressions
                block = self.parse_block()
                left = BlockExpressionNode(left, block)
            else:
                break

        return left
    
    def get_precedence(self, token_type: TokenType) -> int:
        precedences = {
            TokenType.OR: 1,
            TokenType.AND: 2,
            TokenType.EQUAL_EQUAL: 3,
            TokenType.NOT_EQUAL: 3,
            TokenType.GREATER_THAN: 4,
            TokenType.GREATER_EQUAL: 4,
            TokenType.LESS_THAN: 4,
            TokenType.LESS_EQUAL: 4,
            TokenType.PLUS: 5,
            TokenType.MINUS: 5,
            TokenType.MULTIPLY: 6,
            TokenType.DIVIDE: 6,
            TokenType.MODULO: 6,
            TokenType.MAPS_TO: 3,
            TokenType.QUESTION: 0,  # Lowest precedence for ternary
        }
        return precedences.get(token_type, -1)
    
    def parse_primary(self) -> ASTNode:
        token = self.current_token
        if token.type == TokenType.NUMBER:
            self.consume(TokenType.NUMBER)
            if '.' in token.value:
                return LiteralNode(float(token.value))
            else:
                return LiteralNode(int(token.value))
        elif token.type == TokenType.STRING:
            self.consume(TokenType.STRING)
            return LiteralNode(token.value)
        elif token.type == TokenType.LBRACKET:
            # List literal
            self.consume(TokenType.LBRACKET)
            elements = []
            if not self.match(TokenType.RBRACKET):
                while True:
                    element = self.parse_expression()
                    elements.append(element)
                    if self.match(TokenType.COMMA):
                        self.consume(TokenType.COMMA)
                    else:
                        break
            self.consume(TokenType.RBRACKET)
            return ListNode(elements)
        elif token.type == TokenType.LBRACE:
            # Object literal
            return self.parse_object()
        elif token.type == TokenType.IDENTIFIER:
            identifier = self.consume(TokenType.IDENTIFIER).value
            node = IdentifierNode(identifier)
            while True:
                if self.match(TokenType.DOT):
                    self.consume(TokenType.DOT)
                    attr_name = self.consume(TokenType.IDENTIFIER).value
                    node = AttributeAccessNode(node, attr_name)
                elif self.match(TokenType.LPAREN):
                    self.consume(TokenType.LPAREN)
                    args = []
                    if not self.match(TokenType.RPAREN):
                        while True:
                            arg = self.parse_expression()
                            args.append(arg)
                            if self.match(TokenType.COMMA):
                                self.consume(TokenType.COMMA)
                            else:
                                break
                    self.consume(TokenType.RPAREN)
                    node = FunctionCallNode(node, args)
                else:
                    break
            return node
        elif token.type == TokenType.LPAREN:
            self.consume(TokenType.LPAREN)
            expr = self.parse_expression()
            self.consume(TokenType.RPAREN)
            return expr
        elif token.type == TokenType.TRUE:
            self.consume(TokenType.TRUE)
            return LiteralNode(True)
        elif token.type == TokenType.FALSE:
            self.consume(TokenType.FALSE)
            return LiteralNode(False)
        elif token.type == TokenType.NULL:
            self.consume(TokenType.NULL)
            return LiteralNode(None)
        else:
            raise SyntaxError(f"Unexpected token {token.type} ('{token.value}') at line {token.line} column {token.column}")
    
    def parse_parameter_list(self) -> List[Variable]:
        params = []
        if self.match(TokenType.RPAREN):
            return params
        while True:
            param_name = self.consume(TokenType.IDENTIFIER).value
            self.consume(TokenType.COLON)
            param_type = self.parse_type_annotation()
            params.append(Variable(param_name, param_type))
            if not self.match(TokenType.COMMA):
                break
            self.consume(TokenType.COMMA)
        return params
    
    def parse_type_annotation(self) -> CustomType:
        token = self.current_token
        if token.type in (TokenType.IDENTIFIER, TokenType.STRING):
            type_name = self.consume(token.type).value
            is_nullable = False
            if self.match(TokenType.QUESTION):
                self.consume(TokenType.QUESTION)
                is_nullable = True
            # Handle union types
            union_types = []
            while self.match(TokenType.PIPE):
                self.consume(TokenType.PIPE)
                union_type_token = self.current_token
                if union_type_token.type in (TokenType.IDENTIFIER, TokenType.STRING):
                    union_type_name = self.consume(union_type_token.type).value
                    union_types.append(CustomType(union_type_name))
                else:
                    # Consume the unexpected token to prevent infinite loop
                    self.consume(union_type_token.type)
                    raise SyntaxError(f"Unexpected token {union_type_token.type} in type annotation at line {union_type_token.line}")
            if union_types:
                union_types.insert(0, CustomType(type_name))
                return CustomType(name='', union_types=union_types, is_nullable=is_nullable)
            return CustomType(name=type_name, is_nullable=is_nullable)
        else:
            # Consume the unexpected token to prevent infinite loop
            self.consume(token.type)
            raise SyntaxError(f"Unexpected token {token.type} in type annotation at line {token.line}")
    
    def parse_block(self) -> BlockNode:
        self.consume(TokenType.LBRACE)
        self.block_level += 1  # Increment block level
        statements = []
        while not self.match(TokenType.RBRACE):
            if self.current_token.type in (TokenType.IDENTIFIER, TokenType.STRING):
                # Handle key-value pairs with colons
                stmt = self.parse_key_value_or_statement()
            else:
                stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        self.consume(TokenType.RBRACE)
        self.block_level -= 1  # Decrement block level
        return BlockNode(statements)
    
    def parse_object(self) -> ObjectNode:
        self.consume(TokenType.LBRACE)
        attributes = {}
        while not self.match(TokenType.RBRACE):
            stmt = self.parse_key_value_or_statement()
            if isinstance(stmt, KeyValueNode):
                attributes[stmt.key] = stmt.value
            elif isinstance(stmt, TypeInstanceNode):
                attributes[stmt.label] = stmt
            elif isinstance(stmt, NamedBlockNode):
                attributes[stmt.name] = stmt.block
            else:
                pass  # Handle other AST nodes if necessary

            # Allow optional commas in objects
            if self.match(TokenType.COMMA):
                self.consume(TokenType.COMMA)
            else:
                # No comma, continue parsing key-value pairs
                pass

        self.consume(TokenType.RBRACE)
        return ObjectNode(attributes)

    def parse_list(self) -> ListNode:
        self.consume(TokenType.LBRACKET)
        elements = []
        while True:
            if self.match(TokenType.RBRACKET):
                break
            element = self.parse_expression()
            elements.append(element)
            if self.match(TokenType.COMMA):
                self.consume(TokenType.COMMA)
                # Continue to next element
            elif self.match(TokenType.RBRACKET):
                break
            else:
                # Allow for optional commas
                continue
        self.consume(TokenType.RBRACKET)
        return ListNode(elements)
    
    def parse_named_block(self) -> NamedBlockNode:
        name_token = self.consume(TokenType.IDENTIFIER)
        label = None
        if self.match(TokenType.STRING):
            label_token = self.consume(TokenType.STRING)
            label = label_token.value

        if name_token.value in ["configuration", "containers"]:
            # Treat the block content as raw text
            raw_content = self.consume_raw_block()
            return RawBlockNode(name=name_token.value, label=label, content=raw_content)
        else:
            block = self.parse_block()
            return NamedBlockNode(name=name_token.value, label=label, block=block)
    
    def parse_key_value_or_statement(self) -> ASTNode:
        key_token = self.current_token

        if key_token.type in (TokenType.IDENTIFIER, TokenType.STRING, TokenType.TYPE):
            self.consume(key_token.type)
            label = None
            # Check if the next token is a STRING (i.e., a label)
            if self.match(TokenType.STRING):
                label_token = self.consume(TokenType.STRING)
                label = label_token.value
            if self.match(TokenType.COLON):
                self.consume(TokenType.COLON)
                # Check if the next token is an identifier followed by a block
                if self.current_token.type == TokenType.IDENTIFIER and self.peek().type == TokenType.LBRACE:
                    type_name = self.consume(TokenType.IDENTIFIER).value
                    block = self.parse_block()
                    return TypeInstanceNode(label=key_token.value, type_name=type_name, block=block)
                else:
                    # Regular key-value pair with colon
                    value = self.parse_expression_or_block()
                    return KeyValueNode(key=key_token.value, value=value)
            elif self.match(TokenType.EQUALS):
                self.consume(TokenType.EQUALS)
                value = self.parse_expression_or_block()
                return KeyValueNode(key=key_token.value, value=value)
            elif self.match(TokenType.LBRACE):
                # It's a nested block without a type annotation
                block = self.parse_block()
                return NamedBlockNode(name=key_token.value, label=label, block=block)
            else:
                # Not a key-value pair or a block
                self.pos -= 1  # Rewind to parse as statement
                return self.parse_statement()
        else:
            return self.parse_statement()
        
    def parse_expression_or_block(self) -> ASTNode:
        if self.match(TokenType.LBRACE):
            return self.parse_object()
        else:
            return self.parse_expression()
        
    def peek(self, offset=1) -> Optional[Token]:
        if self.pos + offset < len(self.tokens):
            return self.tokens[self.pos + offset]
        return None

# ------------------------------
# Transpiler Implementation
# ------------------------------

class HCLTranspiler(ASTVisitor):
    def __init__(self, type_registry: TypeRegistry):
        self.indent_level = 0
        self.indent_str = "  "
        self.output = ""
        self.type_registry = type_registry
        self.functions = {} 
        self.mappings = {}

    def transpile(self, ast: ASTNode) -> str:
        if isinstance(ast, BlockNode):
            result = ""
            for idx, stmt in enumerate(ast.statements):
                if isinstance(stmt, TypeDefNode):
                    continue
                stmt_str = stmt.accept(self)
                if stmt_str:
                    if idx > 0:
                        result += "\n"  # Add a newline between statements
                    result += stmt_str
            return result.strip()
        else:
            return ast.accept(self)

    def indent(self) -> str:
        return self.indent_str * self.indent_level

    def visit_block(self, node: BlockNode, include_braces: bool = True) -> str:
        """Handle block formatting with optional braces"""
        # Special handling for empty blocks
        if not node.statements:
            return "{}" if include_braces else ""

        # Check if this is the root block
        is_root = self.indent_level == 0

        if include_braces and not is_root:
            result = "{\n"
            self.indent_level += 1
        else:
            result = ""

        for idx, stmt in enumerate(node.statements):
            stmt_str = stmt.accept(self)
            if stmt_str:
                if is_root and include_braces:
                    if idx > 0:
                        result += "\n\n"  # Add extra newline between root-level blocks
                    result += stmt_str
                else:
                    result += self.indent() + stmt_str + "\n"

        if include_braces and not is_root:
            self.indent_level -= 1
            result += self.indent() + "}"

        return result.rstrip()

    def visit_resource(self, node: ResourceNode) -> str:
        """Handles resource blocks with declaration on a single line"""
        def process_block_recursively(block: BlockNode, variables=None) -> BlockNode:
            if variables is None:
                variables = {}
            new_statements = []
            for stmt in block.statements:
                if isinstance(stmt, KeyValueNode):
                    key = stmt.key
                    value = self._node_to_values(stmt.value, variables)
                    variables[key] = value  # Update variables

                    # Check if the value is a dict with a 'type' key
                    if isinstance(value, dict) and 'type' in value:
                        type_name = value.pop('type')
                        # Apply type defaults and calculated fields
                        complete_values = self.type_registry.apply_defaults(
                            type_name,
                            value,
                            evaluator=lambda expr, vars=variables: self.evaluate_expression(expr, vars)
                        )
                        new_value_node = self._value_to_node(complete_values)
                    else:
                        new_value_node = self._value_to_node(value)
                    new_statements.append(KeyValueNode(key, new_value_node))

                elif isinstance(stmt, NamedBlockNode):
                    # Recursively process the nested block
                    new_block = process_block_recursively(stmt.block, variables)
                    new_statements.append(NamedBlockNode(stmt.name, stmt.label, new_block))
                else:
                    new_statements.append(stmt)
            return BlockNode(new_statements)

        # Process the entire block structure
        node.block = process_block_recursively(node.block)

        # Format the output
        result = f'resource "{node.type}" "{node.name}" ' + "{\n"
        
        # Handle block content
        self.indent_level += 1
        content_lines = node.block.accept(self).split('\n')[1:-1]  # Skip braces
        for line in content_lines:
            if line.strip():
                result += self.indent() + line.strip() + "\n"
        self.indent_level -= 1
        result += "}"
        
        return result
            
    def _node_to_values(self, node: ASTNode, variables=None) -> Any:
        if variables is None:
            variables = {}
        if isinstance(node, ObjectNode):
            # Check for custom type
            if 'type' in node.attributes:
                type_attr = node.attributes['type']
                if isinstance(type_attr, IdentifierNode):
                    type_name = type_attr.name
                elif isinstance(type_attr, LiteralNode):
                    type_name = type_attr.value
                else:
                    raise ValueError(f"Unsupported type value: {type_attr}")

                # Convert attributes to values
                values = {}
                local_variables = variables.copy()
                for key, value in node.attributes.items():
                    if key != 'type':
                        val = self._node_to_values(value, local_variables)
                        values[key] = val
                        local_variables[key] = val  # Update local variables

                # Apply type defaults and calculated fields
                complete_values = self.type_registry.apply_defaults(
                    type_name,
                    values,
                    evaluator=lambda expr, vars=local_variables: self.evaluate_expression(expr, vars)
                )
                return complete_values
            else:
                # Regular object
                result = {}
                for key, value in node.attributes.items():
                    val = self._node_to_values(value, variables)
                    result[key] = val
                    variables[key] = val  # Update variables
                return result
        elif isinstance(node, LiteralNode):
            return self.evaluate_expression(node, variables)
        elif isinstance(node, IdentifierNode):
            return variables.get(node.name, node.name)
        elif isinstance(node, ExpressionNode):
            return self.evaluate_expression(node, variables)
        else:
            raise NotImplementedError(f"Cannot convert node type: {type(node)} to value")
        
    def _node_to_values_block(self, block: BlockNode, variables) -> Dict[str, Any]:
        values = {}
        for stmt in block.statements:
            if isinstance(stmt, KeyValueNode):
                key = stmt.key
                value = self._node_to_values(stmt.value, variables)
                values[key] = value
                variables[key] = value  # Update variables
            elif isinstance(stmt, NamedBlockNode):
                value = self._node_to_values(stmt.block, variables)
                values[stmt.name] = value
                variables[stmt.name] = value  # Update variables
        return values

    def _values_to_block(self, values: Dict[str, Any]) -> BlockNode:
        statements = []
        for key, value in values.items():
            if isinstance(value, dict):
                # Handle nested objects
                nested_block = self._values_to_block(value)
                statements.append(NamedBlockNode(
                    name=key,
                    label=None,
                    block=nested_block
                ))
            else:
                statements.append(KeyValueNode(
                    key=key,
                    value=LiteralNode(value)
                ))
        return BlockNode(statements)
    
    def _value_to_node(self, value: Any) -> ASTNode:
        if isinstance(value, dict):
            return ObjectNode({
                k: self._value_to_node(v) for k, v in value.items()
            })
        elif isinstance(value, list):
            return ListNode([self._value_to_node(v) for v in value])
        elif isinstance(value, str):
            return LiteralNode(value)
        elif isinstance(value, (int, float, bool)):
            return LiteralNode(value)
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

    def visit_for_loop(self, node: ForLoopNode) -> str:
        iterable = node.iterable.accept(self)
        loop_var = node.iterator
        result = f'dynamic "{loop_var}" {{\n'
        self.indent_level += 1
        result += f'{self.indent()}for_each = {iterable}\n'
        result += f'{self.indent()}content {node.body.accept(self)}\n'
        self.indent_level -= 1
        result += f'{self.indent()}}}'
        return result

    def visit_if(self, node: IfNode) -> str:
        condition = node.condition.accept(self)
        then_block = node.then_block.accept(self)
        if node.else_block:
            else_block = node.else_block.accept(self)
            return f'dynamic "conditional" {{\n{self.indent_str}for_each = {condition} ? [1] : [0]\n{self.indent_str}content {then_block}\n{self.indent_str}else {else_block}\n{self.indent()}}}'
        else:
            return f'dynamic "conditional" {{\n{self.indent_str}for_each = {condition} ? [1] : []\n{self.indent_str}content {then_block}\n{self.indent()}}}'

    def visit_switch(self, node: SwitchNode) -> str:
        # Convert switch to conditional expressions
        value = node.value.accept(self)
        conditions = []
        for case_value, case_block in node.cases:
            condition = f"{value} == {case_value.accept(self)}"
            block = case_block.accept(self)
            conditions.append(f"{condition} ? {block}")
        if node.default:
            default_block = node.default.accept(self)
            conditions.append(default_block)
        result = " : ".join(conditions)
        return result

    def visit_function(self, node: FunctionNode) -> str:
        # Store the function definition
        self.functions[node.name] = node

        # Map functions to locals with their return expression as a template
        result = f'locals {{\n'
        self.indent_level += 1
        for stmt in node.body.statements:
            if isinstance(stmt, ReturnNode):
                # Assuming the return expression is a LiteralNode or a string with interpolations
                return_expr = stmt.value.accept(self)
                result += f'{self.indent()}{node.name} = {return_expr}\n'
        self.indent_level -= 1
        result += f'}}'
        return result

    def visit_type_def(self, node: TypeDefNode) -> str:
        result = f'# Type {node.name} definition\n'
        for field in node.fields:
            field_line = f'#   {field.name}: {self._type_to_string(field.type)}'
            if field.default_value:
                default_value_str = field.default_value.accept(self)
                field_line += f' = {default_value_str}'
            result += field_line + '\n'
        return result

    def _type_to_string(self, type_def: CustomType) -> str:
        if type_def.union_types:
            # Preserve quotes around string union types
            union_strings = []
            for t in type_def.union_types:
                if t.name in ['string', 'bool', 'number']:
                    union_strings.append(t.name)
                else:
                    union_strings.append(f'"{t.name}"')
            type_str = " | ".join(union_strings)
        else:
            type_str = type_def.name
        if type_def.is_nullable:
            type_str += "?"
        return type_str

    def visit_variable_assignment(self, node: VariableAssignmentNode) -> str:
        value = node.value.accept(self)
        return f'{node.name} = {value}'

    def visit_expression(self, node: ExpressionNode) -> str:
        if node.operator and node.right:
            left = node.left.accept(self)
            right = node.right.accept(self)
            op = node.operator.value
            return f'{left} {op} {right}'
        else:
            return node.left.accept(self)

    def visit_return(self, node: ReturnNode) -> str:
        value = node.value.accept(self)
        return f"return {value}"

    def visit_range(self, node: RangeNode) -> str:
        args = ', '.join(arg.accept(self) for arg in node.arguments)
        return f'{node.function_name}({args})'

    def visit_literal(self, node: LiteralNode) -> str:
        if node.value is None:
            return "null"
        elif isinstance(node.value, str):
            # Use json.dumps to properly escape special characters
            import json
            return json.dumps(node.value)
        elif isinstance(node.value, bool):
            return "true" if node.value else "false"
        else:
            return str(node.value)

    def visit_identifier(self, node: IdentifierNode) -> str:
        return node.name

    def visit_function_call(self, node: FunctionCallNode) -> str:
        func_name = node.function.name if isinstance(node.function, IdentifierNode) else None
        if func_name and func_name in self.functions:
            function_def = self.functions[func_name]
            args = [self.evaluate_expression(arg) for arg in node.arguments]

            # Create a mapping of parameter names to argument values
            param_map = {}
            for param, arg in zip(function_def.params, args):
                param_map[param.name] = arg

            # Evaluate the return expression with the parameter map
            try:
                return_value = self.evaluate_expression_with_params(function_def.body, param_map)
                # Ensure the return value is properly quoted if it's a string
                if isinstance(return_value, str):
                    if not (return_value.startswith('"') and return_value.endswith('"')):
                        return f'"{return_value}"'
                    return return_value
                elif isinstance(return_value, bool):
                    return "true" if return_value else "false"
                elif return_value is None:
                    return "null"
                else:
                    return str(return_value)
            except Exception as e:
                # If evaluation fails, fallback to local reference or keep as is
                pass

        # Fallback: Keep the function call as-is
        func = node.function.accept(self)
        args = ', '.join(arg.accept(self) for arg in node.arguments)
        return f'{func}({args})'
            
    def evaluate_expression_with_params(self, node: ASTNode, params: Dict[str, Any]) -> Any:
        """
        Evaluate an ASTNode expression with a given parameter mapping.
        This is a simplistic evaluator for demonstration purposes.
        """
        if isinstance(node, BlockNode):
            for stmt in node.statements:
                if isinstance(stmt, ReturnNode):
                    return self.evaluate_expression_with_params(stmt.value, params)
            raise ValueError("No return statement found in function body.")
        elif isinstance(node, ReturnNode):
            return self.evaluate_expression_with_params(node.value, params)
        elif isinstance(node, LiteralNode):
            if isinstance(node.value, str):
                # Handle interpolated strings like "${var1}.${var2}"
                def replace_match(match):
                    var_name = match.group(1)
                    return str(params.get(var_name, ''))
                
                interpolated = re.sub(r'\$\{(\w+)\}', replace_match, node.value)
                return interpolated
            elif isinstance(node.value, bool):
                return "true" if node.value else "false"
            else:
                return node.value
        elif isinstance(node, IdentifierNode):
            # Look up the variable in params
            return params.get(node.name, node.name)
        elif isinstance(node, ExpressionNode):
            left = self.evaluate_expression_with_params(node.left, params)
            right = self.evaluate_expression_with_params(node.right, params) if node.right else None
            op = node.operator.value if node.operator else None
            if op == '+':
                return left + right
            elif op == '-':
                return left - right
            elif op == '==':
                return left == right
            elif op == '!=':
                return left != right
            elif op == '>':
                return left > right
            elif op == '>=':
                return left >= right
            elif op == '<':
                return left < right
            elif op == '<=':
                return left <= right
            elif op == '&&':
                return left and right
            elif op == '||':
                return left or right
            else:
                raise ValueError(f"Unsupported operator: {op}")
        elif isinstance(node, TernaryExpressionNode):
            condition = self.evaluate_expression_with_params(node.condition, params)
            if condition:
                return self.evaluate_expression_with_params(node.true_expr, params)
            else:
                return self.evaluate_expression_with_params(node.false_expr, params)
        elif isinstance(node, AttributeAccessNode):
            # For simplicity, concatenate object and attribute with a dot
            obj = self.evaluate_expression_with_params(node.object, params)
            return f"{obj}.{node.attribute}"
        elif isinstance(node, FunctionCallNode):
            # Nested function calls are not supported in this simplistic evaluator
            raise NotImplementedError("Nested function calls are not supported in evaluator.")
        else:
            raise NotImplementedError(f"Cannot evaluate node type: {type(node)}")

    def visit_attribute_access(self, node: AttributeAccessNode) -> str:
        obj = node.object.accept(self)
        return f'{obj}.{node.attribute}'

    def visit_list(self, node: ListNode) -> str:
        """Handle list formatting with proper indentation"""
        if not node.elements:
            return "[]"
        
        # For simple lists with primitive values, keep on one line
        if all(isinstance(e, (LiteralNode, IdentifierNode)) for e in node.elements):
            elements = [e.accept(self) for e in node.elements]
            return f"[{', '.join(elements)}]"
        
        # For complex lists, format with proper indentation
        result = "[\n"
        self.indent_level += 1
        
        for i, element in enumerate(node.elements):
            element_str = element.accept(self)
            result += f"{self.indent()}{element_str}"
            if i < len(node.elements) - 1:
                result += ","
            result += "\n"
                
        self.indent_level -= 1
        result += self.indent() + "]"
        return result

    def visit_object(self, node: ObjectNode) -> str:
        """Handle object formatting with proper indentation"""
        if not node.attributes:
            return "{}"
                
        result = "{\n"
        self.indent_level += 1
        
        # Process each attribute
        for i, (key, value) in enumerate(node.attributes.items()):
            key_str = key
            if not self.is_valid_hcl_identifier(key):
                key_str = f'"{key}"'
            value_str = value.accept(self)
            if isinstance(value, (ObjectNode, ListNode)):
                result += f"{self.indent()}{key_str} = {value_str}\n"
            else:
                result += f"{self.indent()}{key_str} = {value_str}\n"
            
        self.indent_level -= 1
        result += self.indent() + "}"
        return result
    
    def is_complex_node(self, node: ASTNode) -> bool:
        """Determine if a node should be formatted as a complex (multi-line) structure"""
        if isinstance(node, ListNode):
            return not self.is_simple_list(node)
        elif isinstance(node, ObjectNode):
            return not self.is_simple_object(node)
        elif isinstance(node, BlockNode):
            return len(node.statements) > 1
        return False

    def visit_named_block(self, node: NamedBlockNode) -> str:
        """Format named blocks like 'deployment' with mappings directly."""
        name = node.name
        label = f' "{node.label}"' if node.label else ''
        
        # Special handling for 'deployment' block
        if name == 'deployment':
            # Collect all MapsToNode mappings
            for stmt in node.block.statements:
                if isinstance(stmt, MapsToNode):
                    stmt.accept(self)  # This populates self.mappings
            
            # Start the deployment block
            result = f"{name}{label} {{\n"
            self.indent_level += 1

            # Inject the mappings block if mappings exist
            if self.mappings:
                mappings_str = self.format_mappings()
                result += f"{self.indent()}{mappings_str}\n"
                self.mappings.clear()  # Clear after injecting

            # Process other statements excluding MapsToNode
            for stmt in node.block.statements:
                if isinstance(stmt, MapsToNode):
                    continue  # Already handled
                stmt_str = stmt.accept(self)
                if stmt_str.strip():
                    result += self.indent() + stmt_str + "\n"
            
            self.indent_level -= 1
            result += self.indent() + "}"
            return result
        
        # Handle other named blocks normally
        result = f"{name}{label} {{\n"
        self.indent_level += 1
        for stmt in node.block.statements:
            stmt_str = stmt.accept(self)
            if stmt_str.strip():
                result += self.indent() + stmt_str + "\n"
        self.indent_level -= 1
        result += self.indent() + "}"
        return result

    def format_mappings(self) -> str:
        """Format the mappings dictionary into HCL syntax."""
        result = 'mappings = {\n'
        self.indent_level += 1
        for key, value in self.mappings.items():
            # Ensure keys are quoted
            formatted_key = f'"{key}"' if not self.is_valid_hcl_identifier(key) else key
            formatted_value = f'"{value}"' if isinstance(value, str) else str(value)
            result += f"{self.indent()}{formatted_key} = {formatted_value}\n"
        self.indent_level -= 1
        result += self.indent() + "}"
        return result

    def _extract_module_label(self, block: BlockNode) -> Optional[str]:
        """
        Extract the module label from the block statements.
        This function assumes that the first statement is the service name.
        Adjust as per your AST structure.
        """
        for stmt in block.statements:
            if isinstance(stmt, TypeInstanceNode):
                return stmt.label
            elif isinstance(stmt, KeyValueNode):
                # Handle other cases if necessary
                pass
        return None

    def visit_key_value(self, node: KeyValueNode) -> str:
        """Handle key-value pairs with proper formatting"""
        key = node.key
        if not self.is_valid_hcl_identifier(key):
            key = f'"{key}"'
        value = node.value.accept(self)

        # If value is a complex structure (object or array), format appropriately
        if isinstance(node.value, (ObjectNode, ListNode, BlockNode)):
            return f"{key} = {value}"

        return f"{key} = {value}"
    
    def visit_expression_statement(self, node: ExpressionNode) -> str:
        if isinstance(node.left, IdentifierNode) and node.left.name == "service":
            # Handle service blocks specially
            return self.format_service_block(node)
        return super().visit_expression_statement(node)
    
    def format_service_block(self, node: BlockExpressionNode) -> str:
        """Special formatting for service blocks"""
        # Extract service name from the block
        service_name = None
        for stmt in node.block.statements:
            if isinstance(stmt, KeyValueNode) and stmt.key == "name":
                service_name = stmt.value.accept(self)
                break
        
        # Format the service declaration on a single line
        result = f'service "web_app" {{\n'
        
        # Handle block content
        self.indent_level += 1
        content_lines = node.block.accept(self).split('\n')[1:-1]  # Skip braces
        for line in content_lines:
            if line.strip():
                result += self.indent() + line.strip() + "\n"
        self.indent_level -= 1
        result += "}"
        
        return result
    
    def is_simple_list(self, node: ListNode) -> bool:
        """Determine if a list can be formatted on a single line"""
        if not isinstance(node, ListNode):
            return False
        if len(node.elements) > 3:  # More than 3 elements -> complex
            return False
        return all(isinstance(element, (LiteralNode, IdentifierNode)) or
                  (isinstance(element, ListNode) and len(element.elements) <= 3)
                  for element in node.elements)

    
    def is_simple_object(self, node: ObjectNode) -> bool:
        """Determine if an object can be formatted on a single line"""
        if len(node.attributes) > 3:  # More than 3 attributes -> complex
            return False
        return all(isinstance(value, (LiteralNode, IdentifierNode)) or 
                  (isinstance(value, ListNode) and self.is_simple_list(value))
                  for value in node.attributes.values())

    def visit_ternary_expression(self, node: TernaryExpressionNode) -> str:
        condition = node.condition.accept(self)
        true_expr = node.true_expr.accept(self)
        false_expr = node.false_expr.accept(self)
        return f'{condition} ? {true_expr} : {false_expr}'

    def visit_type_instance(self, node: TypeInstanceNode) -> str:
        """Handles type instances with declaration on a single line"""
        label = f' "{node.label}"' if node.label else ''
        block_content = node.block.accept(self)
        
        # Keep type instance declaration on one line
        result = f'type = {node.type_name}{label} ' + "{\n"
        
        # Handle block content
        self.indent_level += 1
        content_lines = block_content.split('\n')[1:-1]  # Skip braces
        for line in content_lines:
            if line.strip():
                result += self.indent() + line.strip() + "\n"
        self.indent_level -= 1
        result += "}"
        
        return result

    def evaluate_expression(self, node: ASTNode, variables=None) -> Any:
        if variables is None:
            variables = {}
        if isinstance(node, LiteralNode):
            if isinstance(node.value, str):
                # Handle interpolated strings like "${var1}.${var2}"
                def replace_match(match):
                    var_name = match.group(1)
                    return str(variables.get(var_name, ''))
                
                interpolated = re.sub(r'\$\{(\w+)\}', replace_match, node.value)
                return interpolated
            else:
                return node.value
        elif isinstance(node, IdentifierNode):
            return variables.get(node.name, node.name)
        elif isinstance(node, ExpressionNode):
            left = self.evaluate_expression(node.left, variables)
            right = self.evaluate_expression(node.right, variables) if node.right else None
            op = node.operator.value if node.operator else None
            if op == '+':
                return left + right
            elif op == '.':
                return f"{left}.{right}"
            elif op == '==':
                return left == right
            elif op == '!=':
                return left != right
            elif op == '>':
                return left > right
            elif op == '>=':
                return left >= right
            elif op == '<':
                return left < right
            elif op == '<=':
                return left <= right
            elif op == '&&':
                return left and right
            elif op == '||':
                return left or right
            else:
                raise NotImplementedError(f"Operator {op} not implemented in evaluator.")
        elif isinstance(node, TernaryExpressionNode):
            condition = self.evaluate_expression(node.condition, variables)
            if condition:
                return self.evaluate_expression(node.true_expr, variables)
            else:
                return self.evaluate_expression(node.false_expr, variables)
        else:
            raise NotImplementedError(f"Cannot evaluate node type: {type(node)}")
        
    def visit_block_expression(self, node: BlockExpressionNode) -> str:
        """Handles block expressions with the expression and opening brace on same line"""
        if isinstance(node.expression, IdentifierNode) and node.expression.name == "service":
            # Special handling for service blocks
            return self.format_service_block(node)
        
        # Regular block expression handling
        expr = node.expression.accept(self)
        
        # Start block on same line as expression 
        result = f'{expr} ' + "{\n"
        
        # Handle block content
        self.indent_level += 1
        content_lines = node.block.accept(self).split('\n')[1:-1]  # Skip braces
        for line in content_lines:
            if line.strip():
                result += self.indent() + line.strip() + "\n"
        self.indent_level -= 1
        result += "}"
        
        return result
    
    def consume_raw_block(self) -> str:
        content = ''
        self.consume(TokenType.LBRACE)  # Consume the initial LBRACE
        brace_count = 1
        while self.pos < len(self.tokens) and brace_count > 0:
            token = self.current_token
            if token.type == TokenType.LBRACE:
                brace_count += 1
            elif token.type == TokenType.RBRACE:
                brace_count -= 1
                if brace_count == 0:
                    self.pos += 1  # Consume the final RBRACE
                    break
            content += token.value + ' '
            self.pos += 1
        return content.strip()
        
    def visit_raw_block(self, node: RawBlockNode) -> str:
        label = f' "{node.label}"' if node.label else ''
        return f'{node.name}{label} {{\n{node.content}\n{self.indent()}}}'
    
    def indent_multiline_string(self, s: str) -> str:
        if not s:
            return s
        lines = s.split('\n')
        # Don't indent the first line if it starts with {
        if lines[0].strip().startswith('{'):
            return lines[0] + '\n' + '\n'.join(self.indent() + line if line.strip() else line 
                                              for line in lines[1:])
        return '\n'.join(self.indent() + line if line.strip() else line for line in lines)

    
    def indent_multiline_string(self, s: str) -> str:
        lines = s.split('\n')
        return '\n'.join(self.indent() + line if line else line for line in lines)

    def visit_maps_to(self, node: MapsToNode) -> None:
        """Collect MapsTo mappings without emitting output directly."""
        source = node.source.accept(self).strip('"')
        target = node.target.accept(self).strip('"')
        self.mappings[source] = target

    def is_valid_hcl_identifier(self, key: str) -> bool:
        """Check if a key is a valid HCL identifier."""
        return re.match(r'^[a-zA-Z_][a-zA-Z0-9_-]*$', key) is not None

# ------------------------------
# Transpiler Conversion Function
# ------------------------------

def convert_enhanced_hcl_to_standard(file_path: str) -> str:
    """
    Converts an enhanced HCL file to standard HCL.

    Args:
        file_path (str): The path to the enhanced HCL file.

    Returns:
        str: The transpiled standard HCL content.
    
    Raises:
        FileNotFoundError: If the file at file_path does not exist.
        IOError: If there's an issue reading the file.
        ParseError: If the HCL content cannot be parsed.
        TranspileError: If there's an issue during transpilation.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            enhanced_hcl = file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file at {file_path} was not found.")
    except IOError as e:
        raise IOError(f"An error occurred while reading the file: {e}")

    # Initialize the lexer with the HCL content
    lexer = EnhancedHCLLexer(enhanced_hcl)
    tokens = lexer.tokenize()

    # Initialize the parser with the tokens
    parser = EnhancedHCLParser(tokens)
    ast = parser.parse()

    transformer = ASTTransformer(parser.type_registry)
    transformed_ast = transformer.transform(ast)

    # Initialize the transpiler with the parser's type registry
    transpiler = HCLTranspiler(parser.type_registry)

    standard_hcl = transpiler.transpile(transformed_ast)
    return standard_hcl

# hcl_content = convert_enhanced_hcl_to_standard("fully_deployable_IaC/input.cloud")
# print(hcl_content)
# parsed_hcl = hcl2.loads(hcl_content)
# print(f"Passed test for: {hcl_content}")

# ------------------------------
# Test Cases
# ------------------------------

def run_transpiler_tests():
    """Run comprehensive tests for the transpiler with better error handling"""
    class TranspilerTest:
        def __init__(self):
            self.passed = 0
            self.failed = 0
        
        def assert_transpile(self, input_hcl: str, expected_output: str, test_name: str):
            try:
                result = convert_enhanced_hcl_to_standard(input_hcl)
                # Normalize whitespace for comparison
                result_norm = ' '.join(result.split())
                expected_norm = ' '.join(expected_output.split())
                
                if result_norm == expected_norm:
                    print(f"✓ {test_name}")
                    self.passed += 1
                else:
                    print(f"✗ {test_name}")
                    print("Expected:")
                    print(expected_output)
                    print("Got:")
                    print(result)
                    self.failed += 1
            except Exception as e:
                print(f"✗ {test_name}")
                print(f"Error: {str(e)}")
                self.failed += 1
    
    test = TranspilerTest()


    test.assert_transpile(
        """
        type ComputeInstance {
            cpu: number = 0,
            memory: number = 0,
            os: string = "Linux"
        }

        type Instance {
            base: ComputeInstance,
            name: string = "default-name",
            size: "t2.micro" | "t2.small" = "t2.micro"
        }
        
        resource "aws_instance" "web" {
            type = Instance
            name = "web-1"
        }
        """,
        """
resource "aws_instance" "web" {
  name = "web-1"
  cpu = 0
  memory = 0
  os = "Linux"
  size = "t2.micro"
}
        """,
        "Type with Base and Defaults"
    )

    test.assert_transpile(
        """
        type ComputedInstance {
            name: string,
            domain: string,
            fqdn: string = calc { "${name}.${domain}" }
        }
        
        resource "aws_instance" "api" {
            type = ComputedInstance
            name = "api"
            domain = "example.com"
        }
        """,
        
"""resource "aws_instance" "api" {
  name = "api"
  domain = "example.com"
  fqdn = "api.example.com"
}"""
        ,
        "Computed Fields"
    )


    test.assert_transpile(
        """
        resource "aws_instance" "web" {
            for i in range(1, 3) {
                name = "web-${i}"
                instance_type = "t2.micro"
            }
        }
        """,
        """
resource "aws_instance" "web" {
  dynamic "i" {
    for_each = range(1, 3)
    content {
      name = "web-${i}"
      instance_type = "t2.micro"
    }
  }
}
        """,
        "Basic For Loop"
    )


    test.assert_transpile(
        """
        type Instance {
            name: string
            size: "t2.micro" | "t2.small"
        }
        
        resource "aws_instance" "web" {
            name = "web-1"
            size = "t2.micro"
        }
        """,
        """
resource "aws_instance" "web" {
  name = "web-1"
  size = "t2.micro"
}
        """,
        "Type Definition"
    )

    
    test.assert_transpile(
        """
        resource "aws_instance" "env" {
            switch var.environment {
                case "prod" { instance_type = "t2.medium" }
                default { instance_type = "t2.micro" }
            }
        }
        """,
        """
resource "aws_instance" "env" {
  var.environment == "prod" ? {
    instance_type = "t2.medium"
  } : {
    instance_type = "t2.micro"
  }
}
        """,
        "Switch Statement"
    )


    test.assert_transpile(
        """
        function make_tags(env: string) {
            return {
                Environment = env
                Managed = "terraform"
            }
        }
        
        resource "aws_instance" "app" {
            tags = local.make_tags
        }
        """,
        """
locals {
  make_tags = {
    Environment = env
    Managed = "terraform"
  }
}

resource "aws_instance" "app" {
  tags = local.make_tags
}
        """,
        "Custom Function"
    )


    test.assert_transpile(
        """
        resource "aws_security_group" "multi_port" {
            for port in [80, 443, 8080] {
                for cidr in var.allowed_cidrs {
                    if cidr != "0.0.0.0/0" {
                        ingress {
                            from_port = port
                            to_port = port
                            protocol = "tcp"
                            cidr_blocks = [cidr]
                        }
                    }
                }
            }
        }
        """,
        """
resource "aws_security_group" "multi_port" {
  dynamic "port" {
    for_each = [80, 443, 8080]
    content {
      dynamic "cidr" {
        for_each = var.allowed_cidrs
        content {
          dynamic "conditional" {
            for_each = cidr != "0.0.0.0/0" ? [1] : []
            content {
              ingress {
                from_port = port
                to_port = port
                protocol = "tcp"
                cidr_blocks = [cidr]
              }
            }
          }
        }
      }
    }
  }
}
        """,
        "Nested Loops"
    )

    test.assert_transpile(
        """
        resource "aws_instance" "conditional_instance" {
            instance_type = var.is_production ? "t2.large" : "t2.micro"
            ami = var.is_production ? "ami-prod" : "ami-dev"
        }
        """,
        """
resource "aws_instance" "conditional_instance" {
  instance_type = var.is_production ? "t2.large" : "t2.micro"
  ami = var.is_production ? "ami-prod" : "ami-dev"
}
        """,
        "Ternary Expression in Resource"
    )
    
  
    test.assert_transpile(
        """
        type DatabaseConfig {
            engine: "postgres" | "mysql" | "sqlite"
            version: string?
            storage: number = 20
        }
        
        resource "aws_db_instance" "default" {
            type = DatabaseConfig
            engine = "postgres"
            version = "12.3"
        }
        """,
        """
resource "aws_db_instance" "default" {
  engine = "postgres"
  version = "12.3"
  storage = 20
}
        """,
        "Type with Union and Nullable Types"
    )
    

    test.assert_transpile(
        """
        type ServiceConfig {
            name: string
            port: number
            description: string? = "Default service description"
        }
        
        resource "aws_service" "my_service" {
            type = ServiceConfig
            name = "my-service"
            port = 8080
        }
        """,
        """
resource "aws_service" "my_service" {
  name = "my-service"
  port = 8080
  description = "Default service description"
}
        """,
        "Nullable Field with Default"
    )
    
    print(f"\nTests completed: {test.passed} passed, {test.failed} failed")

enhanced_hcl = """
type ComputeInstance {
    cpu: number = 4
    memory: number = 16
    os: string = "Linux"
}

type Instance {
    base: ComputeInstance
    name: string = "default-instance"
    size: "t2.micro" | "t2.small" = "t2.micro"
}

service "web_app" {
    type = "application"
    dependencies = []

    infrastructure {
        compute = [
            {
                type = Instance
                name = "web_server"
                count = 2
                size = "t2.micro"
                os = "ami-0abcdef1234567890" 
                tags = {
                    Environment = "production"
                    Role        = "web"
                }
                provisioners = [
                    {
                        type = "remote-exec"
                        inline = [
                            "sudo apt-get update -y",
                            "sudo apt-get install -y nginx",
                            "sudo systemctl start nginx",
                            "sudo systemctl enable nginx"
                        ]
                    }
                ]
            }
        ]
    }

    configuration {
        packages = ["nginx", "curl"]
        services = {
            running = ["nginx"]
            enabled = ["nginx"]
        }
        variables = {
            server_port = 80
        }
        files = {
            "/etc/nginx/sites-available/default" = "templates/nginx_default.conf"
        }
    }

    containers = [
        {
            name        = "web_container"
            image       = "nginx:latest"
            ports       = [80]
            environment = {
                NGINX_HOST = "localhost"
                NGINX_PORT = "80"
            }
            replicas    = 3
            health_check = {
                http_get = {
                    path = "/"
                    port = 80
                }
                initial_delay_seconds = 15
                period_seconds        = 20
            }
            resources = {
                limits = {
                    cpu    = "500m"
                    memory = "256Mi"
                }
                requests = {
                    cpu    = "250m"
                    memory = "128Mi"
                }
            }
        }
    ]
}
"""

# standard_hcl = convert_enhanced_hcl_to_standard(enhanced_hcl)

# # Write the output to a file named "running.hcl"
# with open("runner.hcl", "w") as file:
#     file.write(standard_hcl)

# run_transpiler_tests()