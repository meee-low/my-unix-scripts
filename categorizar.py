#!/usr/bin/env python3

import csv
import argparse
from io import TextIOWrapper
import pathlib
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Divide o arquivo CSV em múltiplos arquivos, filtrado baseado em uma coluna específica conter uma string."
    )
    parser.add_argument(
        "input",
        help="Arquivo CSV de entrada (default: stdin)",
        type=argparse.FileType("r"),
        default=sys.stdin,
    )

    parser.add_argument(
        "--coluna",
        type=int,
        required=True,
        help="Índice da Coluna que deve corresponder às strings (começa em 0).",
    )

    parser.add_argument(
        "--strings",
        nargs="+",
        required=True,
        help="Strings usadas para filtrar/classificar.",
    )

    parser.add_argument(
        "--stdout",
        help="Usar o stdout como saída. (Apenas permitido para 1 string)",
        action="store_true",
        default=True,
    )

    parser.add_argument(
        "--outdir",
        help="Diretório onde salvar os arquivos csv.",
        type=pathlib.Path,
        default=pathlib.Path.cwd(),
    )

    parser.add_argument(
        "--n-linhas-cabecalho",
        type=int,
        default=1,
        help="O número linhas para pular (cabeçalho)",
    )

    args = parser.parse_args()

    data = args.input.read()
    lines = data.splitlines()
    sample = lines[0]

    sniffer = csv.Sniffer()
    dialect = sniffer.sniff(sample, ";")
    reader = csv.reader(lines, dialect)

    header = [next(reader) for _ in range(args.n_linhas_cabecalho)]

    writers: dict[str, csv.Writer] = {}
    files: dict[str, TextIOWrapper[_]] = {}

    try:
        for s in args.strings:
            if len(args.strings) == 1 and args.stdout:
                out = sys.stdout
            else:
                parent_path = pathlib.Path(args.outdir)
                parent_path.mkdir(parents=True, exist_ok=True)
                path = parent_path / f"{s}.csv"
                out = open(path, "w", newline="")
                files[s] = out

            writer = csv.writer(out, dialect)
            writers[s] = writer

            writer.writerows(header)

        for i, row in enumerate(reader):
            try:
                key_cell = row[args.coluna]
            except IndexError:
                raise Exception(
                    f"Valor de coluna ruim. Recebeu {args.coluna}, mas a linha {i} só tem {len(row)} colunas."
                )
            for s in args.strings:
                if s in key_cell:
                    writers[s].writerow(row)
    finally:
        for f in files.values():
            f.close()


if __name__ == "__main__":
    main()
