"""
Command-Line TOA5-to-CSV Tool
-----------------------------

The following is a command-line interface to convert a TOA5 file's headers to a
single row, which makes it more suitable for processing in other programs that
expect CSV files with a single header row.

If this module and its scripts have been installed correctly, you should be able
to run ``toa5-to-csv --help`` or ``python -m toa5.to_csv --help`` for details.

Author, Copyright, and License
------------------------------

Copyright (c) 2023-2024 Hauke Dämpfling (haukex@zero-g.net)
at the Leibniz Institute of Freshwater Ecology and Inland Fisheries (IGB),
Berlin, Germany, https://www.igb-berlin.de/

This library is free software: you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This library is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program. If not, see https://www.gnu.org/licenses/
"""
import csv
import sys
import json
import argparse
import fileinput
from typing import Optional, Sequence
from igbpyutils.file import open_out
from igbpyutils.error import init_handlers
from .. import read_header, ColumnHeader, ColumnHeaderTransformer, default_col_hdr_transform

def _arg_parser():
    parser = argparse.ArgumentParser('toa5.to_csv', description='TOA5 to CSV Converter')
    parser.add_argument('-o', '--out-file', help="Output filename")
    parser.add_argument('-l', '--env-line', metavar='ENV_LINE_FILE', help="JSON file to write environment line to")
    parser.add_argument('-d', '--out-dialect', help="Output CSV dialect (see Python `csv` documentation)",
                        choices=csv.list_dialects(), default='excel')
    parser.add_argument('-n', '--simple-names', help="Don't add units etc. to column names", action="store_true")
    parser.add_argument('-e', '--in-encoding', help="Input file encoding (default UTF-8)", default="UTF-8")
    parser.add_argument('-c', '--out-encoding', help="Output encoding (default UTF-8)", default="UTF-8")
    parser.add_argument('-t', '--require-timestamp', help="Require first column to be TIMESTAMP", action="store_true")
    parser.add_argument('-j', '--allow-jagged', help="Allow rows to have differing column counts", action="store_true")
    parser.add_argument('toa5file', metavar='TOA5FILE', help="The TOA5 file to process", nargs='?')
    return parser

def main(argv :Optional[Sequence[str]] = None):
    init_handlers()
    parser = _arg_parser()
    args = parser.parse_args(argv)

    if args.in_encoding!='UTF-8' and (not args.toa5file or args.toa5file=='-'):
        parser.error('Can only use --in-encoding when specifying an input file')
    if args.out_encoding!='UTF-8' and (not args.out_file or args.out_file=='-'):
        parser.error('Can only use --out-encoding when specifying an output file')
    col_trans :ColumnHeaderTransformer = (lambda col: col.name) if args.simple_names else default_col_hdr_transform

    if sys.hexversion >= 0x03_0A_00_00:  # cover-req-ge3.10
        enc = { "encoding": args.in_encoding }
    else:  # cover-req-lt3.10
        enc = { "openhook": fileinput.hook_encoded(args.in_encoding) }
    with (fileinput.input((args.toa5file,) if args.toa5file else (), **enc) as ifh,  # pyright: ignore [reportCallIssue, reportArgumentType]
          open_out(args.out_file, encoding=args.out_encoding, newline='') as ofh):
        csv_rd = csv.reader(ifh, strict=True)
        csv_wr = csv.writer(ofh, dialect=args.out_dialect)
        env_line, columns = read_header(csv_rd)
        if args.require_timestamp and columns[0] != ColumnHeader(name='TIMESTAMP', unit='TS'):
            raise ValueError("First column was not a timestamp (if that's not an error, turn off `require_timestamp0`)")
        csv_wr.writerow( col_trans(c) for c in columns )
        #TODO Later: That the following pragma is needed on Python 3.12+ appears to be a regression in Coverage.py
        # from 7.6.1 -> 7.6.2; keep an eye on whether that gets fixed
        for ri, row in enumerate(csv_rd, start=5):  # pragma: no branch
            if not args.allow_jagged and len(row)!=len(columns):
                raise ValueError(f"Row {ri}: expected {len(columns)} columns but got {len(row)}")
            csv_wr.writerow(row)

    if args.env_line:
        with open_out(args.env_line, encoding=args.out_encoding) as fh:
            json.dump(env_line._asdict(), fp=fh, indent=2)

    parser.exit(0)
