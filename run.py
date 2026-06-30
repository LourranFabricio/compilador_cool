"""
run.py

Script de automação do pipeline COOL -> Bril -> Execução.

Fluxo:
 1. Leitura do arquivo fonte `.cl` (padrão: `arquivo.txt`).
 2. Parsing via `parser.parse_code`.
 3. Análise semântica via `semantic.SemanticAnalyzer`.
 4. Geração Bril via `codegen.emit_bril_from_ast` (gera `saida.json`).
 5. Validação: executa `bril2txt saida.json` (se disponível) e imprime versão legível.
 6. Execução: executa `deno run brili.ts saida.json` (se `deno` + `brili.ts` disponíveis).

Use: `python run.py --input meu_programa.cl --out saida.json`
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Pipeline COOL -> Bril -> Execução')
    parser.add_argument('--input', '-i', default='arquivo.cool', help='Arquivo fonte COOL')
    parser.add_argument('--out', '-o', default='saida.json', help='Arquivo JSON Bril de saída')
    parser.add_argument('--bril2txt', default='bril2txt', help='Comando bril2txt (se disponível)')
    parser.add_argument('--brili', default='brili.ts', help='Caminho para brili.ts (Deno)')
    args = parser.parse_args()

    src_path = Path(args.input)
    if not src_path.exists():
        print(f"Arquivo de entrada não encontrado: {src_path}")
        sys.exit(1)

    # 1. Ler fonte
    src = src_path.read_text(encoding='utf-8')

    # 2. Parser
    try:
        from parser import parse_code
    except Exception as e:
        print('Erro importando parser:', e)
        sys.exit(1)

    ast = parse_code(src)
    if not ast:
        print('Erro: parser retornou AST vazia.')
        sys.exit(1)

    # 3. Semantic
    try:
        from semantic import SemanticAnalyzer
    except Exception as e:
        print('Erro importando semantic:', e)
        sys.exit(1)

    analyzer = SemanticAnalyzer(ast)
    errors = analyzer.analyze()
    if errors:
        print('Erros semânticos detectados:')
        for e in errors:
            print('-', e)
        sys.exit(1)

    # 4. Codegen
    try:
        from codegen import emit_bril_from_ast
    except Exception as e:
        print('Erro importando codegen:', e)
        sys.exit(1)

    out_path = args.out
    prog = emit_bril_from_ast(ast, out_path)
    print(f'Gerado Bril JSON em: {out_path}')

    # 5. Validação (bril2txt)
    try:
        p = subprocess.run([args.bril2txt, out_path], capture_output=True, text=True, check=False)
        if p.returncode == 0:
            print('\n--- Bril (legível) ---')
            print(p.stdout)
        else:
            print('\n(bril2txt retornou erro ou não existe)')
            if p.stderr:
                print(p.stderr)
    except FileNotFoundError:
        print('\nbril2txt não encontrado no PATH; pulei a validação legível.')

    # 6. Execução com Deno + brili.ts
    try:
        run_cmd = ['deno', 'run', args.brili, out_path]
        p2 = subprocess.run(run_cmd, capture_output=True, text=True, check=False)
        print('\n--- Execução (brili) ---')
        if p2.stdout:
            print(p2.stdout)
        if p2.stderr:
            print(p2.stderr, file=sys.stderr)
        if p2.returncode != 0:
            print(f'brili retornou código de saída {p2.returncode}')
    except FileNotFoundError:
        print('\nDeno não encontrado; não foi possível executar `deno run brili.ts`.')


if __name__ == '__main__':
    main()
