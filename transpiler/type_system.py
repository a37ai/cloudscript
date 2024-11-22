from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
from .ast_nodes import ASTNode, ASTVisitor
from .tokentypes import TokenType
import re

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
