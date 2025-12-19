#!/usr/bin/env python3
# /// script
# dependencies = [
# "openpyxl"
# ]
# ///

import csv
import openpyxl
import argparse
import os
import pathlib


def try_parse_number(value: str) -> str | float | int:
    value = value.strip()
    try:
        f = float(value.replace(",", "."))
        i = int(f)
        if i == f:
            return i
        return f
    except ValueError:
        return value


def csv_to_xlsx(csv_files, output_file):
    # Create a new Excel workbook
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove the default sheet created

    for csv_file in csv_files:
        # Read CSV
        with open(csv_file, newline="") as f:
            sample = f.readline()
            f.seek(0)

            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, ";")
            reader = csv.reader(f, dialect)
            sheet_name = os.path.splitext(os.path.basename(csv_file))[0]

            # Create a new sheet for this CSV file
            sheet = wb.create_sheet(title=sheet_name)

            # Write rows to sheet
            for row in reader:
                sheet.append([try_parse_number(cell) for cell in row])

            print(f"Added {csv_file} as sheet '{sheet_name}'")

    # Save the workbook to an Excel file
    wb.save(output_file)
    print(f"All CSVs have been written to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Combine multiple CSV files into a single Excel file, with each CSV on a separate sheet."
    )

    parser.add_argument(
        "csv_files", type=pathlib.Path, nargs="+", help="List of CSV files to combine"
    )

    parser.add_argument(
        "output", type=pathlib.Path, help="Output Excel file (e.g., output.xlsx)"
    )

    parser.add_argument("--glob", default="*.csv", help="Glob (default: *.csv)")

    args = parser.parse_args()

    csv_paths: list[pathlib.Path] = []
    for path in args.csv_files:
        if path.is_dir():
            csv_paths.extend(sorted(path.glob(args.glob)))
        elif path.is_file():
            csv_paths.append(path)
        else:
            parser.error(f"Path not found: {path}")

    if not csv_paths:
        parser.error("No CSV files found.")

    csv_to_xlsx(csv_paths, args.output)


if __name__ == "__main__":
    main()
