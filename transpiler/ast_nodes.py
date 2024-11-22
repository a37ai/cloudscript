from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Tuple
from abc import ABC, abstractmethod
from .tokentypes import Token, TokenType

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