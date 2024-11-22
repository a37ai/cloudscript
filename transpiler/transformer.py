from .ast_nodes import ASTNode, ASTVisitor, ObjectNode, ListNode, KeyValueNode, LiteralNode, IdentifierNode, ExpressionNode, TernaryExpressionNode, AttributeAccessNode, FunctionCallNode, NamedBlockNode, BlockNode
from .type_system import TypeRegistry
from typing import Any
import re

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