import ply.yacc as yacc
from lex import tokens, lexer

# precedência dos operadores
precedence = (
    ('right', 'ASSIGN'),
    ('left', 'NOT'),
    ('nonassoc', 'LE', 'LT', 'EQ'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'MULT', 'DIV'),
    ('left', 'ISVOID'),
    ('left', 'TILDE'),
    ('left', 'AT'),
    ('left', 'DOT'),
)

#  estrutura geral de um programa como uma lista de uma ou mais classes
def p_program(p):
    'program : class_list'
    p[0] = ('program', p[1])

#Lista de classes
def p_class_list(p):
    '''class_list : class_list class SEMICOLON
                  | class SEMICOLON'''
    if len(p) == 4:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

# Definição de uma classe, com  nome,herança opcional euma lista de features(atributos e métodos).
def p_class(p):
    '''class : CLASS TYPEID LBRACE feature_list RBRACE
             | CLASS TYPEID INHERITS TYPEID LBRACE feature_list RBRACE'''
    if len(p) == 6: 
        p[0] = ('class', p[2], None, p[4])
    else: 
        p[0] = ('class', p[2], p[4], p[6])

#Lista de features (atributos e métodos).
def p_feature_list(p):
    '''feature_list : feature_list feature SEMICOLON
                    | empty'''
    if len(p) == 4:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = []

# define um método com nome, lista de parâmetros formais, tipo de retorno e corpo da expressão
def p_feature_method(p):
    'feature : OBJECTID LPAREN param_list RPAREN COLON TYPEID LBRACE expr RBRACE'
    p[0] = ('method', p[1], p[3], p[6], p[8])

# Define um atributo com nome, tipo e uma expressão de inicialização opcional.
# atributo com inicialização: ID : TYPE <- expr
def p_feature_attr_assign(p):
    'feature : OBJECTID COLON TYPEID ASSIGN expr'
    p[0] = ('attribute', p[1], p[3], p[5])

# atributo sem inicialização: ID : TYPE
def p_feature_attr(p):
    'feature : OBJECTID COLON TYPEID'
    p[0] = ('attribute', p[1], p[3], None)

# Lista de parâmetros formais (utilizada em métodos).
def p_param_list(p):
    '''param_list : param_list COMMA formal
                  | formal
                  | empty'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    elif len(p) == 2 and p[1] != None:
        p[0] = [p[1]]
    else:
        p[0] = []

# função para lidar com a definição de um parâmetro formal, que é composta por um identificador, dois pontos e um tipo
def p_formal(p):
    'formal : OBJECTID COLON TYPEID'
    p[0] = ('formal', p[1], p[3])


#Atribuição de um valor a um identificador
def p_expr_assign(p):
    'expr : OBJECTID ASSIGN expr'
    p[0] = ('assign', p[1], p[3])

#chama método com dispatch estático (especificando o tipo).
#  expr[@TYPE].ID( [expr] )
def p_expr_dispatch(p):
    '''expr : expr DOT OBJECTID LPAREN arg_list RPAREN
            | expr AT TYPEID DOT OBJECTID LPAREN arg_list RPAREN'''
    if len(p) == 7:
        p[0] = ('dispatch', p[1], None, p[3], p[5])
    else:
        p[0] = ('dispatch', p[1], p[3], p[5], p[7])

#Chamada de método implícita (self dispatch).
# Chamada de método implícita: ID( [expr] )
def p_expr_self_dispatch(p):
    'expr : OBJECTID LPAREN arg_list RPAREN'
    p[0] = ('self_dispatch', p[1], p[3])

# Controle de If
def p_expr_if(p):
    'expr : IF expr THEN expr ELSE expr FI'
    p[0] = ('if', p[2], p[4], p[6])

# Controle de  While
def p_expr_while(p):
    'expr : WHILE expr LOOP expr POOL'
    p[0] = ('while', p[2], p[4])


# blocos de código: { expr; expr; }
def p_expr_block(p):
    'expr : LBRACE expr_list RBRACE'
    p[0] = ('block', p[2])

#Lista de expressões em um bloco
def p_expr_list(p):
    '''expr_list : expr_list expr SEMICOLON
                 | expr SEMICOLON'''
    if len(p) == 4: 
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

#estrutura let para declaração de variáveis locais.
#Let: let ID : TYPE [<- expr], ... in expr
def p_expr_let(p):
    'expr : LET let_bindings IN expr'
    p[0] = ('let', p[2], p[4])

# função para lidar com as ligações de let, permitindo múltiplas ligações ou apenas uma ligação
def p_let_bindings(p):
    '''let_bindings : let_bindings COMMA let_binding
                    | let_binding'''
    if len(p) == 4: 
        p[0] = p[1] + [p[3]]
    else: 
        p[0] = [p[1]]

#função para lidar com uma única ligação de let, que pode ser com ou sem inicialização
def p_let_binding(p):
    '''let_binding : OBJECTID COLON TYPEID ASSIGN expr
                   | OBJECTID COLON TYPEID'''
    if len(p) == 6: 
        p[0] = ('let_bind', p[1], p[3], p[5])
    else:
        p[0] = ('let_bind', p[1], p[3], None)

# Estrutura Case: case expr of [ID : TYPE => expr;]+ esac
def p_expr_case(p):
    'expr : CASE expr OF case_list ESAC'
    p[0] = ('case', p[2], p[4])

#função para lidar com a lista de ramos de case, permitindo múltiplos ramos ou apenas um ramo
def p_case_list(p):
    '''case_list : case_list case_branch
                 | case_branch'''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = [p[1]]

#função para lidar com um único ramo de case, que é composto por um identificador, dois pontos, um tipo, uma seta e uma expressão
def p_case_branch(p):
    'case_branch : OBJECTID COLON TYPEID DARROW expr SEMICOLON'
    p[0] = ('case_branch', p[1], p[3], p[5])

# Criação de uma nova instância de um tipo
def p_expr_new(p):
    'expr : NEW TYPEID'
    p[0] = ('new', p[2])

# verificação se uma expressão é void .
def p_expr_isvoid(p):
    'expr : ISVOID expr'
    p[0] = ('isvoid', p[2])

# Operações Matemáticas
def p_expr_math(p):
    '''expr : expr PLUS expr
            | expr MINUS expr
            | expr MULT expr
            | expr DIV expr'''
    p[0] = ('binary_op', p[2], p[1], p[3])

# Operadores Relacionais
def p_expr_relational(p):
    '''expr : expr LT expr
            | expr LE expr
            | expr EQ expr'''
    p[0] = ('relational_op', p[2], p[1], p[3])

# Operações Lógicas e Unárias
def p_expr_unary(p):
    '''expr : NOT expr
            | TILDE expr'''
    p[0] = ('unary_op', p[1], p[2])

# Parênteses
def p_expr_parens(p):
    'expr : LPAREN expr RPAREN'
    p[0] = p[2]

# Literais e Identificadores
def p_expr_literal(p):
    '''expr : OBJECTID
            | INT_CONST
            | STR_CONST
            | BOOL_CONST
            | SELF'''
    p[0] = ('literal', p[1])

#função para lidar com a lista de argumentos em chamadas de métodos, permitindo múltiplos argumentos ou nenhum argumento
def p_arg_list(p):
    '''arg_list : arg_list COMMA expr
                | expr
                | empty'''
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    elif len(p) == 2 and p[1] != None:
        p[0] = [p[1]]
    else:
        p[0] = []



#função para lidar com produções vazias, que é necessária para permitir listas opcionais de parâmetros, expressões, etc.
def p_empty(p):
    'empty :'
    pass


def p_error(p):
    if p:
        print(f"Erro de sintaxe na linha {p.lineno}, token inesperado: {p.type} ('{p.value}')")
    else:
        print("Erro de sintaxe: Fim de arquivo (EOF) inesperado")


parser = yacc.yacc()

def parse_code(code):
    return parser.parse(code, lexer=lexer)
if __name__ == "__main__":
    filename = 'arquivo.txt'
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()
    except FileNotFoundError:
        print(f"Erro: O arquivo '{filename}' não foi encontrado no diretório.")
        exit(1)
    
    # Chama o parser passando o conteúdo do arquivo
    ast = parse_code(code)
    
    # Imprime a Árvore Sintática (AST) gerada
    if ast is not None:
        print("\nÁrvore Sintática (AST):\n")
        import pprint
        pprint.pprint(ast)