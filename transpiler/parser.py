from typing import List, Optional, Dict, Any
from .tokentypes import Token, TokenType
from .ast_nodes import *
from .type_system import TypeRegistry, FieldDefinition, CustomType, TypeConstraint, CalculatedField, TypeDefinition

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