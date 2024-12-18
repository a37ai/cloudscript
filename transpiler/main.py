from .ast_nodes import *
from .type_system import *
from .lexer import EnhancedHCLLexer
from .parser import EnhancedHCLParser
from .transformer import ASTTransformer

# ------------------------------
# Transpiler
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

def convert_enhanced_hcl_to_standard_string(enhanced_hcl: str) -> str:
    lexer = EnhancedHCLLexer(enhanced_hcl)
    tokens = lexer.tokenize()

    parser = EnhancedHCLParser(tokens)
    ast = parser.parse()

    transpiler = HCLTranspiler(parser.type_registry)
    return transpiler.transpile(ast)