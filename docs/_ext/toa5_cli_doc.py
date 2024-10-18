import argparse
import importlib
from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx

class Toa5CsvCli(Directive):
    def run(self):
        toa5_to_csv = importlib.import_module('toa5.to_csv')
        parser = toa5_to_csv._arg_parser()  # pyright: ignore [reportPrivateUsage]  # pylint: disable=protected-access
        # monkey patch this ArgumentParser to fix the output width
        parser._get_formatter = lambda: argparse.HelpFormatter(parser.prog, width=78)  # pylint: disable=protected-access
        return [nodes.literal_block(text=parser.format_help())]

def setup(app: Sphinx):
    app.add_directive('toa5_to_csv_cli_doc', Toa5CsvCli)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
