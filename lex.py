import ply.lex as lex

#Palavra reservadas 
reserved = {
    'class': 'CLASS',
    'else': 'ELSE',
    'fi': 'FI',
    'if': 'IF',
    'in': 'IN',
    'inherits': 'INHERITS',
    'isvoid': 'ISVOID',
    'let': 'LET',
    'loop': 'LOOP',
    'pool': 'POOL',
    'then': 'THEN',
    'while': 'WHILE',
    'case': 'CASE',
    'esac': 'ESAC',
    'new': 'NEW',
    'of': 'OF',
    'not': 'NOT',
}

self = {
    # Casos do self
    'self': 'SELF',            
    'SELF_TYPE': 'SELF_TYPE',  
}

tokens = [
     # Identificadores
    'TYPEID',    # Nomes de classes (começam com Maiúscula)
    'OBJECTID',  # Nomes de variáveis/métodos (começam com minúscula)
    
    # Tipagens
    'INT_CONST',
    'STR_CONST',
    'BOOL_CONST',

     # Operadores e delimitadores
    'ASSIGN',    # <-
    'PLUS',      # +
    'MINUS',     # -
    'MULT',      # *
    'DIV',       # /
    'TILDE',     # ~
    'LT',        # <
    'LE',        # <=
    'EQ',        # =
    'LPAREN',    # (
    'RPAREN',    # )
    'LBRACE',    # {
    'RBRACE',    # }
    'COLON',     # :
    'SEMICOLON', # ;
    'COMMA',     # ,
    'DOT',       # .
    'AT',        # @
    'DARROW',    # =>
] + list(reserved.values()) + list(self.values()) #para adicionar palavras reservadas e casos do self a lista de tokens

# expressões regulares para tokens simples
# A biblioteca PLY associa automaticamente as expressões regulares aos tokens usando a convenção de nomenclatura t_nometoken.
t_ASSIGN = r'<-'
t_PLUS = r'\+'
t_MINUS = r'-'
t_MULT = r'\*'
t_DIV = r'/'
t_TILDE = r'~'
t_LT = r'<'
t_LE = r'<='
t_EQ = r'='
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_LBRACE = r'\{'
t_RBRACE = r'\}'
t_COLON = r':'
t_SEMICOLON = r';'
t_COMMA = r','
t_DOT = r'\.'
t_AT = r'@'
t_DARROW = r'=>'

# Expressões regulares para tokens mais complexos
# O mesmo vale para as funções, basta ter o nome t_nometoken 
def t_TYPEID(t):
    r'[A-Z][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, 'TYPEID')
    return t

def t_BOOL_CONST(t):
    r't[rR][uU][eE]|f[aA][lL][sS][eE]'
    t.value = True if t.value.lower() == 'true' else False
    return t

def t_OBJECTID(t):
    r'[a-z][a-zA-Z0-9_]*'
    # Converte para minúsculo para bater com as chaves do dicionário 'reserved'
    val_lower = t.value.lower()
    if val_lower in reserved:
        t.type = reserved[val_lower]
    else:
        t.type = 'OBJECTID'
    return t


def t_INT_CONST(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_STR_CONST(t):
    r'\"([^\\\n]|(\\.))*?\"'
    content = t.value[1:-1]
    if len(content) > 1024:
        print("Erro: String muito longa!")
        # Lógica de erro aqui
    t.value = content
    return t

# Ignorar espaços e tabs
t_ignore = ' \t'

# Ignorar comentários
t_ignore_COMMENT = r'\(\*(.|\n)*?\*\)'

t_ignore_COMMENTINLINE = r'--.*'

# Função para rastrear números de linha
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Função para lidar com erros de caracteres ilegais
def t_error(t):
    print(f"Caractere Inválido '{t.value[0]}' at line {t.lexer.lineno}")
    t.lexer.skip(1)

lexer = lex.lex()


# Testar o lexer
if __name__ == "__main__":
    filename = 'arquivo.txt'
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = f.read()
    except FileNotFoundError:
        print(f"arquivo não encontrado: {filename}")
        exit(1)
    lexer.input(data)
    for tok in lexer:
        print(tok)
