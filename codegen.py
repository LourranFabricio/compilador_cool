"""
codegen.py

Gera JSON no formato Bril a partir da AST do parser/semantic.

Design e convenções:
- Cada método de classe COOL é flattenado para uma função global `Class_method`.
- O primeiro argumento de cada função gerada é `self` do tipo `ptr`.
- Mapeamento de tipos: `Int` -> `int`, `Bool` -> `bool`, resto -> `ptr`.
- Temporárias geradas por `new_temp()` como `v1`, `v2`, ... para destinos Bril.
- Instruções Bril são representadas como dicionários Python e armazenadas
  em `program['functions'][i]['instrs']`.

Observação: Algumas operações de heap/objeto (get_attr/set_attr/alloc)
ficam modeladas como extensões (dicionários) — adapte conforme seu runtime.
"""
import json
from typing import Dict, List, Any, Optional


class CodeGenerator:
	"""Transforma AST validada em programa Bril (estrutura Python).

	A classe implementa um visitor `gen_expr` que retorna o nome da
	variável temporária (string) que contém o resultado da expressão.
	"""

	def __init__(self, ast: Any):
		self.ast = ast
		self.program: Dict[str, Any] = {"functions": []}
		self.temp_count = 0
		self.label_count = 0
		self.scopes: List[Dict[str, str]] = []  # pilha de escopos nome->var
		self.current_func: Optional[Dict[str, Any]] = None

	# ----------------------- Helpers -----------------------
	def new_temp(self) -> str:
		"""Gera um novo nome de temporária `vN`."""
		self.temp_count += 1
		return f"v{self.temp_count}"

	def new_label(self, base: str = "L") -> str:
		self.label_count += 1
		return f"{base}{self.label_count}"

	def type_map(self, cool_type: str) -> str:
		"""Mapeia tipos COOL para tipos Bril."""
		if cool_type == 'Int':
			return 'int'
		if cool_type == 'Bool':
			return 'bool'
		return 'ptr'

	def emit_instr(self, instr: Dict[str, Any]):
		"""Adiciona uma instrução ao bloco atual da função."""
		if self.current_func is None:
			raise RuntimeError('Tentativa de emitir instrução sem função ativa')
		self.current_func['instrs'].append(instr)

	def push_scope(self):
		self.scopes.append({})

	def pop_scope(self):
		if not self.scopes:
			raise RuntimeError('Pop em pilha de escopos vazia')
		self.scopes.pop()

	def bind_var(self, name: str, varname: str):
		"""Associa `name` à variável `varname` no escopo atual."""
		if not self.scopes:
			self.push_scope()
		self.scopes[-1][name] = varname

	def lookup_var(self, name: str) -> Optional[str]:
		"""Procura `name` nos escopos; retorna None se não existir."""
		for s in reversed(self.scopes):
			if name in s:
				return s[name]
		return None

	# ----------------------- Geração principal -----------------------
	def generate(self) -> Dict[str, Any]:
		if not self.ast or self.ast[0] != 'program':
			raise ValueError('AST inválida para geração de código')

		classes = self.ast[1]
		for cls in classes:
			self.gen_class(cls)

		return self.program

	def gen_class(self, cls_node: Any):
		# cls_node = ('class', name, parent, features)
		_, class_name, _, features = cls_node
		for f in features:
			if f[0] == 'method':
				self.gen_method(class_name, f)
			# atributos são inicializados no construtor/alloc em runtime

	def gen_method(self, class_name: str, method_node: Any):
		#itera sobre os métodos da classe e gera funções Bril correspondentes
		# method_node = ('method', name, params, return_type, body)
		_, mname, params, ret_type, body = method_node
		#cria nome da função Bril como a classe + "_" + nome do método
		func_name = f"{class_name}_{mname}"

		# args: primeiro `self: ptr` representa o objeto atual, depois parâmetros mapeados através do type_map
		args = [{"name": "self", "type": "ptr"}]
		for p in params:
			# p = ('formal', param_name, type)
			args.append({"name": p[1], "type": self.type_map(p[2])})

		#cria um dicionário representando a função Bril e adiciona à lista de funções do programa
		func = {"name": func_name, "args": args, "instrs": [], "returns": [self.type_map(ret_type)]}
		self.program['functions'].append(func)
		self.current_func = func

		# novo escopo e vincula argumentos como variáveis locais
		self.push_scope()
		for a in args:
			# nomes de argumento ficam disponíveis como variáveis locais
			self.bind_var(a['name'], a['name'])

		# Gera o valor de retorno da função a partir do corpo do método
		result = self.gen_expr(body)

		# Emite return: assume 1 valor retornado
		self.emit_instr({"op": "ret", "args": [result]})

		# limpa escopo e função atual
		self.pop_scope()
		self.current_func = None

	# ----------------------- Visitor de expressões -----------------------
	def gen_expr(self, node: Any) -> str:
		"""Gera código para `node` e retorna o nome da variável que contém o resultado.

		O visitor cobre os principais nós produzidos pelo parser/semantic.
		"""
		if node is None:
			tmp = self.new_temp()
			self.emit_instr({"op": "const", "type": "ptr", "value": None, "dest": tmp})
			return tmp

		ntype = node[0]

		# Assign: pode ser local ou atributo (set_attr)
		if ntype == 'assign':
			_, name, expr = node
			val = self.gen_expr(expr)
			#verifica se a variável já existe no escopo atual (local) ou se é um atributo de self
			var = self.lookup_var(name)
			if var:
				# sobrescreve variável local (usa id para copiar)
				self.emit_instr({"op": "id", "args": [val], "dest": var})
				return var
			else:
				# atributo em self (usa set_attr)
				self.emit_instr({"op": "set_attr", "args": ["self", val], "attr": name})
				return val

		# Dispatch / self_dispatch -> call
		if ntype == 'dispatch' or ntype == 'self_dispatch':
			if ntype == 'dispatch':
				# dispatch com objeto explícito: ('dispatch', obj_expr, static_type, method_name, args)
				_, obj_expr, static_t, mname, args = node
				obj = self.gen_expr(obj_expr)
				target_class = static_t or None
				# Se static_t for None, será dispatch dinâmico (dyn_method)
			else:
				_, mname, args = node
				obj = 'self'
				target_class = None

			arg_vals = []
			# self como primeiro argumento
			arg_vals.append('self' if obj == 'self' else obj)
			for a in args:
				arg_vals.append(self.gen_expr(a))
			# Determina o nome da função Bril a ser chamada: se target_class for fornecido, usa Class_method; caso contrário, usa dyn_method (função dinâmica)
			if target_class:
				func_name = f"{target_class}_{mname}"
			else:
				func_name = f"dyn_{mname}"
			# Emite a chamada de função Bril com os argumentos e destino
			dest = self.new_temp()
			self.emit_instr({"op": "call", "func": func_name, "args": arg_vals, "dest": dest})
			return dest

		# If: cria labels, avalia cond, gera branch/jumps e seleciona valor com id
		if ntype == 'if':
			_, cond, then_e, else_e = node
			# Avalia a condição e gera labels para then, else e end
			cond_tmp = self.gen_expr(cond)
			# Gera labels únicos para os blocos then, else e end
			l_then = self.new_label('then')
			l_else = self.new_label('else')
			l_end = self.new_label('end')

			# Emite instrução de branch condicional: se cond_tmp for verdadeiro, vai para l_then; caso contrário, vai para l_else
			self.emit_instr({"op": "br", "args": [cond_tmp], "labels": [l_then, l_else]})

			# Gera o bloco then: avalia then_e, copia resultado para tmp_res e pula para l_end
			self.emit_instr({"label": l_then})
			then_tmp = self.gen_expr(then_e)
			tmp_res = self.new_temp()
			self.emit_instr({"op": "id", "args": [then_tmp], "dest": tmp_res})
			self.emit_instr({"op": "jmp", "labels": [l_end]})

			# Gera o bloco else: avalia else_e, copia resultado para tmp_res
			self.emit_instr({"label": l_else})
			else_tmp = self.gen_expr(else_e)
			self.emit_instr({"op": "id", "args": [else_tmp], "dest": tmp_res})
			self.emit_instr({"label": l_end})
			return tmp_res

		# While
		if ntype == 'while':
			_, cond, body = node
			# Gera labels para loop, body e endloop
			l_loop = self.new_label('loop')
			l_body = self.new_label('body')
			l_end = self.new_label('endloop')
			# Emite label do loop, avalia a condição e gera branch para body ou endloop
			self.emit_instr({"label": l_loop})
			cond_tmp = self.gen_expr(cond)
			# Emite branch condicional: se cond_tmp for verdadeiro, vai para l_body; caso contrário, vai para l_end
			self.emit_instr({"op": "br", "args": [cond_tmp], "labels": [l_body, l_end]})
			# Gera o corpo do loop: avalia body e depois pula de volta para o início do loop
			self.emit_instr({"label": l_body})
			# Gera o corpo do loop e depois pula de volta para o início do loop
			self.gen_expr(body)
			# Pula de volta para o início do loop
			self.emit_instr({"op": "jmp", "labels": [l_loop]})
			# Emite label de fim do loop
			self.emit_instr({"label": l_end})
			tmp = self.new_temp()
			self.emit_instr({"op": "const", "type": "ptr", "value": None, "dest": tmp})
			return tmp

		# Block
		if ntype == 'block':
			_, exprs = node
			res = None
			# Avalia cada expressão do bloco e retorna o resultado da última
			for e in exprs:
				res = self.gen_expr(e)
			return res

		# Let 
		if ntype == 'let':
			_, bindings, body = node
			# Cria um novo escopo para as variáveis let, vincula cada variável e avalia o corpo
			self.push_scope()
			for b in bindings:
				_, name, t, init = b
				mapped = name
				self.bind_var(name, mapped)
				if init:
					# Avalia a expressão de inicialização e emite instrução de atribuição para a variável let
					val = self.gen_expr(init)
					# Emite instrução de atribuição para a variável let
					self.emit_instr({"op": "id", "args": [val], "dest": mapped})
			res = self.gen_expr(body)
			self.pop_scope()
			return res

		# Case  avalia cada ramo e escolhe um resultado
		if ntype == 'case':
			_, expr, branches = node
			self.gen_expr(expr)
			res_tmp = None
			# Avalia cada ramo do case, cria um novo escopo para cada ramo, vincula a variável do ramo e avalia a expressão correspondente. O resultado final é armazenado em res_tmp.
			for br in branches:
				_, var_name, var_type, br_expr = br
				self.push_scope()
				self.bind_var(var_name, var_name)
				val = self.gen_expr(br_expr)
				if res_tmp is None:
					res_tmp = self.new_temp()
					self.emit_instr({"op": "id", "args": [val], "dest": res_tmp})
				self.pop_scope()
			if res_tmp is None:
				res_tmp = self.new_temp()
				self.emit_instr({"op": "const", "type": "ptr", "value": None, "dest": res_tmp})
			return res_tmp

		# New -> alloc
		if ntype == 'new':
			_, tname = node
			# Emite instrução de alocação de objeto do tipo tname e retorna a temporária que contém o ponteiro para o objeto alocado
			tmp = self.new_temp()
			self.emit_instr({"op": "alloc", "type": "ptr", "dest": tmp, "class": tname})
			return tmp

		# isvoid
		if ntype == 'isvoid':
			_, e = node
			# Avalia a expressão e emite instrução de comparação para verificar se o resultado é nulo (None). Retorna uma temporária que contém o valor booleano do resultado.
			self.gen_expr(e)
			tmp = self.new_temp()
			self.emit_instr({"op": "const", "type": "bool", "value": False, "dest": tmp})
			return tmp

		# Binary ops
		if ntype == 'binary_op':
			_, op, l, r = node
			# Avalia os operandos esquerdo e direito, gera uma nova temporária para o resultado e emite a instrução Bril correspondente à operação binária. 
			# Retorna a temporária que contém o resultado da operação.
			lt = self.gen_expr(l)
			rt = self.gen_expr(r)
			dest = self.new_temp()
			# Mapeia operadores binários para operações Bril correspondentes
			op_map = {'+': 'add', '-': 'sub', '*': 'mul', '/': 'div'}
			bril_op = op_map.get(op, 'add')
			self.emit_instr({"op": bril_op, "type": "int", "args": [lt, rt], "dest": dest})
			return dest

		# Relational
		if ntype == 'relational_op':
			_, op, l, r = node
			# Avalia os operandos esquerdo e direito, gera uma nova temporária para o resultado e emite a instrução Bril correspondente à operação relacional.
			#  Retorna a temporária que contém o resultado da operação.
			lt = self.gen_expr(l)
			rt = self.gen_expr(r)
			dest = self.new_temp()
			#
			op_map = {'<': 'lt', '<=': 'le', '=': 'eq'}
			bril_op = op_map.get(op, 'eq')
			self.emit_instr({"op": bril_op, "type": 'bool', "args": [lt, rt], "dest": dest})
			return dest

		# Unary
		if ntype == 'unary_op':
			_, op, e = node
			# Avalia a expressão, gera uma nova temporária para o resultado e emite a instrução Bril correspondente à operação unária (not ou subtração de zero).
			# Retorna a temporária que contém o resultado da operação.
			val = self.gen_expr(e)
			dest = self.new_temp()
			# Mapeia operadores unários para operações Bril correspondentes
			if op == 'not':
				self.emit_instr({"op": "not", "type": "bool", "args": [val], "dest": dest})
			# Se o operador for '-', emite uma instrução de subtração de zero para obter o valor negativo
			else:
				zero = self.new_temp()
				self.emit_instr({"op": "const", "type": "int", "value": 0, "dest": zero})
				self.emit_instr({"op": "sub", "type": "int", "args": [zero, val], "dest": dest})
			return dest

		# Literais
		if ntype == 'literal':
			_, tok_type, val = node
			# Mapeia literais para instruções Bril correspondentes, criando uma nova temporária para armazenar o valor literal e emitindo a instrução Bril 
			# apropriada (const) com o tipo correto (int, bool ou ptr). Retorna a temporária que contém o valor literal.
			if tok_type == 'INT_CONST':
				dest = self.new_temp()
				self.emit_instr({"op": "const", "type": "int", "value": int(val), "dest": dest})
				return dest
			if tok_type == 'BOOL_CONST':
				dest = self.new_temp()
				b = True if str(val).lower() in ('true', '1') else False
				self.emit_instr({"op": "const", "type": "bool", "value": b, "dest": dest})
				return dest
			if tok_type == 'STR_CONST':
				dest = self.new_temp()
				self.emit_instr({"op": "const", "type": "ptr", "value": val, "dest": dest})
				return dest
			if tok_type == 'SELF':
				return 'self'
			if tok_type == 'OBJECTID':
				var = self.lookup_var(val)
				if var:
					return var
				dest = self.new_temp()
				self.emit_instr({"op": "get_attr", "args": ["self"], "attr": val, "dest": dest})
				return dest

		# Default
		tmp = self.new_temp()
		# Emite uma instrução Bril de constante nula (None) para a temporária recém-criada e retorna o nome da temporária.
		self.emit_instr({"op": "const", "type": "ptr", "value": None, "dest": tmp})
		return tmp

	# Esta função é responsável por emitir o programa Bril gerado em formato JSON para um arquivo especificado pelo usuário. 
	# Ela abre o arquivo no modo de escrita com codificação UTF-8 e utiliza a função `json.dump` para escrever o conteúdo do programa Bril
	# (armazenado em `self.program`) no arquivo, garantindo que os caracteres não ASCII sejam preservados e que a saída seja formatada com 
	# indentação de 2 espaços para melhor legibilidade.
	def emit_json(self, filename: str):
		with open(filename, 'w', encoding='utf-8') as f:
			json.dump(self.program, f, ensure_ascii=False, indent=2)

# Função auxiliar para gerar Bril a partir da AST e opcionalmente salvar em arquivo JSON
def emit_bril_from_ast(ast: Any, out_path: Optional[str] = None) -> Dict[str, Any]:
	gen = CodeGenerator(ast)
	prog = gen.generate()
	if out_path:
		gen.emit_json(out_path)
	return prog


if __name__ == '__main__':
	# Modo uso rápido: carrega `arquivo.cool`, gera Bril e imprime JSON
	try:
		from parser import parse_code
		with open('arquivo.cool', 'r', encoding='utf-8') as f:
			src = f.read()
		ast = parse_code(src)
		gen = CodeGenerator(ast)
		prog = gen.generate()
		print(json.dumps(prog, ensure_ascii=False, indent=2))
	except Exception:
		print('Uso: importar emit_bril_from_ast(ast, out_path)')
