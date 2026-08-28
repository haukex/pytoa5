import argparse
import importlib
from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx

class Toa5CsvCli(Directive):
    def run(self) -> list[nodes.Node]:
        toa5_to_csv = importlib.import_module('toa5.to_csv')
        parser = toa5_to_csv._arg_parser()  # pyright: ignore [reportPrivateUsage]  # pylint: disable=protected-access
        parser.formatter_class = lambda prog: argparse.HelpFormatter(prog, width=78)
        return [nodes.literal_block(text=parser.format_help())]

def setup(app: Sphinx) -> dict[str, object]:
    app.add_directive('toa5_to_csv_cli_doc', Toa5CsvCli)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
