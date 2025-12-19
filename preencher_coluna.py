#!/usr/bin/env python3

import sys
import csv
import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from csv import Dialect


def detect_dialect(sample: str) -> "type[Dialect]":
    sniffer = csv.Sniffer()
    return sniffer.sniff(sample)


def fill_down(rows: list[list[str]]):
    previous: list[str | None] = [None] * len(rows[0])

    for row in rows:
        for i, value in enumerate(row):
            if value == "" and previous[i]:
                row[i] = previous[i]
            else:
                previous[i] = value
        yield row


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fill_down",
        description="Preenche células vazias de CSV copiando os valores da linha de cima.",
        usage="fill_down -o <output-file> <input-file>",
    )

    parser.add_argument(
        "input",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Arquivo CSV de entrada",
    )

    parser.add_argument(
        "output",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Arquivo CSV de saída",
    )

    parser.add_argument(
        "--n_linhas_cabecalho",
        type=int,
        default=1,
        help="O número linhas para pular (cabeçalho)",
    )

    args = parser.parse_args()

    data = args.input.read()
    sample = data[:4096]

    dialect = detect_dialect(sample)
    reader = csv.reader(data.splitlines(), dialect)
    writer = csv.writer(args.output, dialect)

    rows = list(reader)
    writer.writerows(rows[: args.n_linhas_cabecalho])
    writer.writerows(fill_down(rows[args.n_linhas_cabecalho :]))


if __name__ == "__main__":
    main()
