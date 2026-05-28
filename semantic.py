class SemanticError(Exception):
    pass

class AttributeInfo:
    def __init__(self, name, type_name):
        self.name = name
        self.type_name = type_name

class MethodInfo:
    def __init__(self, name, params, return_type):
        self.name = name
        self.params = params # lista de (nome, tipo)
        self.return_type = return_type

    def get_signature(self):
        # retorna os tipos dos parametros e o retorno pra comparar no override
        p_types = []
        for p in self.params:
            p_types.append(p[1])
        return (tuple(p_types), self.return_type)

class ClassInfo:
    def __init__(self, name, parent_name=None):
        self.name = name
        self.parent_name = parent_name
        self.attrs = {}
        self.methods = {}

    def add_attr(self, name, type_name):
        self.attrs[name] = AttributeInfo(name, type_name)

    def add_method(self, name, params, return_type):
        self.methods[name] = MethodInfo(name, params, return_type)

class TypeEnvironment:
    def __init__(self):
        # Classes basicas do COOL
        self.classes = {
            'Object': ClassInfo('Object', None),
            'IO': ClassInfo('IO', 'Object'),
            'Int': ClassInfo('Int', 'Object'),
            'Bool': ClassInfo('Bool', 'Object'),
            'String': ClassInfo('String', 'Object')
        }

    def add_class(self, name, parent):
        self.classes[name] = ClassInfo(name, parent)

    def is_defined(self, name):
        return name in self.classes

    def get_parent(self, name):
        if name in self.classes:
            return self.classes[name].parent_name
        return None

    def conforms(self, t1, t2):
        # verifica se t1 herda de t2
        curr = t1
        while curr is not None:
            if curr == t2:
                return True
            curr = self.get_parent(curr)
        return False

    def get_lca(self, types):
        # Ancestral comum mais baixo pra if/case
        if not types: return 'Object'
        
        # monta a lista de heranca de cada tipo
        all_chains = []
        for t in types:
            chain = []
            curr = t
            while curr:
                chain.append(curr)
                curr = self.get_parent(curr)
            all_chains.append(chain)
            
        # o primeiro da lista que ta em todas as outras
        for candidate in all_chains[0]:
            ok = True
            for i in range(1, len(all_chains)):
                if candidate not in all_chains[i]:
                    ok = False
                    break
            if ok: return candidate
        return 'Object'

    def find_method(self, class_name, method_name):
        curr = class_name
        while curr:
            cls = self.classes.get(curr)
            if not cls: break
            if method_name in cls.methods:
                return cls.methods[method_name], curr
            curr = cls.parent_name
        return None

    def find_attr(self, class_name, attr_name):
        curr = class_name
        while curr:
            cls = self.classes.get(curr)
            if not cls: break
            if attr_name in cls.attrs:
                return cls.attrs[attr_name]
            curr = cls.parent_name
        return None

    def check_cycles(self):
        visited = {}
        def check(name):
            if name in visited:
                return visited[name] == 1 # 1 = visitando
            visited[name] = 1
            p = self.get_parent(name)
            if p and check(p): return True
            visited[name] = 2 # 2 = visitado
            return False
        
        for c in list(self.classes.keys()):
            if check(c): return True
        return False

class SemanticAnalyzer:  
    def __init__(self, ast):
        self.ast = ast
        self.env = TypeEnvironment()
        self.errors = []
        self.cur_class = None
        self.scopes = [] # pilha de dicionarios pra variaveis

    def log_error(self, msg):
        self.errors.append(msg)

    def analyze(self):
        if not self.ast or self.ast[0] != 'program':
            self.log_error("Erro: AST bizarra.")
            return self.errors
            
        classes_ast = self.ast[1]
        
        # 1. Coleta as classes
        nomes_vistos = set()
        for c in classes_ast:
            name = c[1]
            parent = c[2] or 'Object'
            if name in nomes_vistos:
                self.log_error(f"Classe {name} ja existe.")
                continue
            nomes_vistos.add(name)
            if name in ['Int', 'Bool', 'String', 'SELF_TYPE']:
                self.log_error(f"Nao pode usar nome reservado {name}.")
            if parent in ['Int', 'Bool', 'String', 'SELF_TYPE']:
                self.log_error(f"Nao pode herdar de {parent}.")
            self.env.add_class(name, parent)

        # 2. Valida hierarquia
        for name, info in self.env.classes.items():
            if info.parent_name and not self.env.is_defined(info.parent_name):
                self.log_error(f"Pai {info.parent_name} da classe {name} nao existe.")
        if self.env.check_cycles():
            self.log_error("Ciclo de heranca detectado!")

        # 3. Coleta atributos e metodos
        for c in classes_ast:
            class_name = c[1]
            features = c[3]
            cls_info = self.env.classes[class_name]
            for f in features:
                tipo_f = f[0]
                nome_f = f[1]
                if nome_f in cls_info.attrs or nome_f in cls_info.methods:
                    self.log_error(f"Membro {nome_f} duplicado na classe {class_name}.")
                    continue
                if tipo_f == 'attribute':
                    cls_info.add_attr(nome_f, f[2])
                else:
                    params = []
                    for p in f[2]:
                        params.append((p[1], p[2]))
                    cls_info.add_method(nome_f, params, f[3])

        # 4. Checa tudo (tipos e escopo)
        for c in classes_ast:
            self.cur_class = c[1]
            for f in c[3]:
                if f[0] == 'attribute':
                    self.check_attr(f)
                else:
                    self.check_method(f)
        return self.errors

    def check_attr(self, f):
        nome, tipo, init = f[1], f[2], f[3]
        if not self.env.is_defined(tipo):
            self.log_error(f"Tipo {tipo} do atributo {nome} nao existe.")
            return
        # COOL nao deixa redefinir atributo ou metodo do pai
        pai = self.env.classes[self.cur_class].parent_name
        if self.env.find_method(pai, nome) or self.env.find_attr(pai, nome):
            self.log_error(f"Atributo {nome} ja existe no pai.")
        if init:
            tipo_init = self.check_expr(init)
            if tipo_init and not self.env.conforms(tipo_init, tipo):
                self.log_error(f"Tipo {tipo_init} nao bate com {tipo} no atributo {nome}.")

    def check_method(self, f):
        nome, params, ret, corpo = f[1], f[2], f[3], f[4]
        if not self.env.is_defined(ret):
            self.log_error(f"Tipo de retorno {ret} nao existe.")
        
        # checa parametros duplicados
        p_nomes = [p[1] for p in params]
        if len(set(p_nomes)) < len(p_nomes):
            self.log_error(f"Parametros repetidos no metodo {nome}.")
            
        # checa override
        pai = self.env.classes[self.cur_class].parent_name
        res_pai = self.env.find_method(pai, nome)
        if res_pai:
            m_pai = res_pai[0]
            m_atual = MethodInfo(nome, [(p[1], p[2]) for p in params], ret)
            if m_pai.get_signature() != m_atual.get_signature():
                self.log_error(f"Override do metodo {nome} ta com assinatura errada.")

        # novo escopo pro metodo
        escopo = {'self': self.cur_class}
        for p in params:
            escopo[p[1]] = p[2]
            if not self.env.is_defined(p[2]):
                self.log_error(f"Tipo {p[2]} do parametro {p[1]} nao existe.")
        
        self.scopes.append(escopo)
        tipo_corpo = self.check_expr(corpo)
        self.scopes.pop()
        
        if tipo_corpo and not self.env.conforms(tipo_corpo, ret):
            self.log_error(f"Corpo do metodo {nome} retorna {tipo_corpo} mas devia ser {ret}.")

    def get_var_type(self, name):
        # busca na pilha de escopos (do mais novo pro mais velho)
        for s in reversed(self.scopes):
            if name in s: return s[name]
        # se nao achar, tenta ver se e atributo da classe
        attr = self.env.find_attr(self.cur_class, name)
        if attr: return attr.type_name
        return None

    def check_expr(self, expr):
        tipo_no = expr[0]
        
        if tipo_no == 'assign':
            nome, e = expr[1], expr[2]
            tipo_var = 'Object' if nome == 'self' else self.get_var_type(nome)
            if nome == 'self':
                self.log_error("Nao pode mudar o self.")
            elif tipo_var is None:
                self.log_error(f"Variavel {nome} nao declarada.")
                tipo_var = 'Object'
            tipo_val = self.check_expr(e)
            if tipo_val and not self.env.conforms(tipo_val, tipo_var):
                self.log_error(f"Atribuicao errada: {tipo_val} nao entra em {tipo_var}.")
            return tipo_var

        if tipo_no in ['dispatch', 'self_dispatch']:
            if tipo_no == 'dispatch':
                obj, estatico, nome_m, args = expr[1], expr[2], expr[3], expr[4]
                tipo_obj = self.check_expr(obj)
            else:
                nome_m, args = expr[1], expr[2]
                tipo_obj, estatico = self.cur_class, None
            
            alvo = estatico or tipo_obj
            if estatico:
                if not self.env.is_defined(estatico) or not self.env.conforms(tipo_obj, estatico):
                    self.log_error(f"Tipo estatico {estatico} invalido.")
                    alvo = 'Object'
            
            res_m = self.env.find_method(alvo, nome_m)
            if not res_m:
                self.log_error(f"Metodo {nome_m} nao existe na classe {alvo}.")
                return 'Object'
            
            m_info = res_m[0]
            if len(args) != len(m_info.params):
                self.log_error(f"Metodo {nome_m} precisa de {len(m_info.params)} args.")
            else:
                for i in range(len(args)):
                    t_arg = self.check_expr(args[i])
                    t_param = m_info.params[i][1]
                    if t_arg and not self.env.conforms(t_arg, t_param):
                        self.log_error(f"Argumento {i} devia ser {t_param} mas e {t_arg}.")
            
            if m_info.return_type == 'SELF_TYPE':
                return tipo_obj
            return m_info.return_type

        if tipo_no == 'if':
            if self.check_expr(expr[1]) != 'Bool':
                self.log_error("Condicao do if tem que ser Bool.")
            t1 = self.check_expr(expr[2])
            t2 = self.check_expr(expr[3])
            return self.env.get_lca([t1, t2])

        if tipo_no == 'while':
            if self.check_expr(expr[1]) != 'Bool':
                self.log_error("Condicao do while tem que ser Bool.")
            self.check_expr(expr[2])
            return 'Object'

        if tipo_no == 'block':
            res = 'Object'
            for e in expr[1]:
                res = self.check_expr(e)
            return res

        if tipo_no == 'let':
            self.scopes.append({})
            for _, n, t, init in expr[1]:
                if not self.env.is_defined(t):
                    self.log_error(f"Tipo {t} no let nao existe.")
                    t = 'Object'
                if n in self.scopes[-1]:
                    self.log_error(f"Variavel {n} repetida no let.")
                self.scopes[-1][n] = t
                if init:
                    t_init = self.check_expr(init)
                    if t_init and not self.env.conforms(t_init, t):
                        self.log_error(f"Inicializacao do let nao bate: {t_init} vs {t}.")
            res = self.check_expr(expr[2])
            self.scopes.pop()
            return res

        if tipo_no == 'case':
            self.check_expr(expr[1])
            tipos_ramos = []
            vistos = set()
            for _, n, t, e in expr[2]:
                if not self.env.is_defined(t):
                    self.log_error(f"Tipo {t} no case nao existe.")
                    t = 'Object'
                if t in vistos:
                    self.log_error(f"Tipo {t} repetido no case.")
                vistos.add(t)
                self.scopes.append({n: t})
                tipos_ramos.append(self.check_expr(e))
                self.scopes.pop()
            return self.env.get_lca(tipos_ramos)

        if tipo_no == 'new':
            t = expr[1]
            if not self.env.is_defined(t):
                self.log_error(f"Tipo {t} no new nao existe.")
                return 'Object'
            return t

        if tipo_no == 'isvoid':
            self.check_expr(expr[1])
            return 'Bool'

        if tipo_no in ['binary_op', 'relational_op']:
            op = expr[1]
            l = self.check_expr(expr[2])
            r = self.check_expr(expr[3])
            if op in ['+', '-', '*', '/', '<', '<=']:
                if l != 'Int' or r != 'Int':
                    self.log_error(f"Operador {op} so aceita Int.")
                return 'Int' if tipo_no == 'binary_op' else 'Bool'
            if op == '=':
                basicos = ['Int', 'Bool', 'String']
                if (l in basicos or r in basicos) and l != r:
                    self.log_error("Comparacao de tipos basicos tem que ser igual.")
                return 'Bool'

        if tipo_no == 'unary_op':
            op = expr[1]
            st = self.check_expr(expr[2])
            if op == 'not' and st != 'Bool':
                self.log_error("not so aceita Bool.")
            if op == '~' and st != 'Int':
                self.log_error("~ so aceita Int.")
            return 'Bool' if op == 'not' else 'Int'

        if tipo_no == 'literal':
            l_tipo = expr[1]
            val = expr[2]
            if l_tipo == 'BOOL_CONST': return 'Bool'
            if l_tipo == 'INT_CONST': return 'Int'
            if l_tipo == 'STR_CONST': return 'String'
            if l_tipo == 'SELF': return self.cur_class
            if l_tipo == 'OBJECTID':
                v_tipo = self.get_var_type(val)
                if v_tipo is None:
                    self.log_error(f"Variavel {val} nao existe.")
                    return 'Object'
                return v_tipo
        return 'Object'

if __name__ == '__main__':
    from parser import parse_code
    filename = 'arquivo.txt'
    try:
        f = open(filename, 'r', encoding='utf-8')
        source = f.read()
        f.close()
    except:
        print("Erro ao abrir arquivo.")
        exit(1)

    ast = parse_code(source)
    if not ast:
        print('Erro no parser.')
        exit(1)

    analyzer = SemanticAnalyzer(ast)
    erros = analyzer.analyze()
    if erros:
        print('Deu erro semantico:')
        for e in erros:
            print('-', e)
    else:
        print('Tudo certo!')
