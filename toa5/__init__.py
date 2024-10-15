"""
TODO: Document

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
import re
import csv
import importlib
from typing import NamedTuple
from collections.abc import Iterator, Sequence, Generator, Callable
from igbpyutils.iter import no_duplicates, zip_strict

class Toa5Error(RuntimeError):
    """An error class for :func:`read_header`."""

class EnvironmentLine(NamedTuple):
    """Represents a TOA5 "Environment Line", giving details about the data logger and its program."""
    station_name :str
    logger_model :str
    logger_serial :str
    logger_os :str
    program_name :str
    program_sig :str
    table_name :str

class ColumnHeader(NamedTuple):
    """Named tuple representing a column header.

    This class represents a column header as it would be read from a text file, therefore,
    when fields are empty, this is represented by empty strings, not by ``None``.
    """
    #: Column name
    name :str
    #: Scientific/engineering units (optional)
    unit :str = ""
    #: Data process (optional; examples:  ``"Smp"``, ``"Avg"``, ``"Max"``, etc.)
    prc :str = ""

#: A type for a function that takes a :class:`ColumnHeader` and turns it into a single string. See :func:`default_col_hdr_transform`.
ColumnHeaderTransformer = Callable[[ColumnHeader], str]

#: A table of shorter versions of common units, used in :func:`default_col_hdr_transform`.
SHORTER_UNITS = {
    "meters/second": "m/s",
    "Deg C": "°C",
    "oC": "°C",
    "Volts": "V",
    "m^3/m^3": "m³/m³",
    "W/m^2": "W/m²",
    "Watts/meter^2": "W/m²",
    "nSec": "ns",
    "uSec": "μs",
    "hours": "hr",
    "micrometer": "μm",
    "degrees": "°",
    "Deg": "°",
    "unitless": ""
}

def _maybe_prc(col :ColumnHeader, sep :str) -> str:
    if col.prc and col.prc.lower()!='smp' and not re.search(re.escape(col.prc)+r'(?:\(\d+\))?\Z', col.name, re.I):
        return col.name + sep + col.prc
    return col.name

_sql_parens_re = re.compile(r'\((\d+)\)\Z')
def sql_col_hdr_transform(col :ColumnHeader) -> str:
    """TODO: Doc"""
    return _sql_parens_re.sub(r'_\1', _maybe_prc(col, '_') ).lower()

def default_col_hdr_transform(col :ColumnHeader):
    """The default function used to transform a :class:`ColumnHeader` into a single string.

    This conversion is slightly opinionated and will:

    - append :attr:`ColumnHeader.prc` with a slash (unless the name already ends with it or it is "Smp"),
    - shorten some units (:data:`SHORTER_UNITS`),
    - use square brackets around the units, and
    - ignore the "TS" and "RN" "units" on the "TIMESTAMP" and "RECORD" columns, respectively.
    """
    c = _maybe_prc(col, '/')
    if col.unit and \
            not ( col.name=='TIMESTAMP' and col.unit=='TS' or col.name=='RECORD' and col.unit=='RN' ) \
            and len(SHORTER_UNITS.get(col.unit, col.unit)):
        c += "[" + SHORTER_UNITS.get(col.unit, col.unit) + "]"
    return c

#: A short alias for :func:`default_col_hdr_transform`.
short_name = default_col_hdr_transform

_env_line_keys = ('toa5',) + EnvironmentLine._fields
def read_header(csv_reader :Iterator[Sequence[str]]) -> tuple[EnvironmentLine, tuple[ColumnHeader, ...]]:
    """Read the header of a TOA5 file.

    A common use case to read a TOA5 file would be the following; as you can see the main difference
    between reading a regular CSV file and a TOA5 file is the additional call to this function.

    >>> import csv
    >>> import toa5
    >>> with open('Example.dat', encoding='ASCII', newline='') as fh:
    ...     csv_rd = csv.reader(fh, strict=True)
    ...     env_line, columns = toa5.read_header(csv_rd)
    ...     print([ toa5.short_name(col) for col in columns ])
    ...     for row in csv_rd:
    ...         print(row)
    ['TIMESTAMP', 'RECORD', 'BattV_Min[V]']
    ['2021-06-19 00:00:00', '0', '12.99']
    ['2021-06-20 00:00:00', '1', '12.96']

    :param csv_reader: TODO Doc
    :return: TODO Doc
    :raises Toa5Error: TODO Doc
    """
    # ### Read the environment line
    try:
        env_line = next(csv_reader)
    except StopIteration as ex:
        raise Toa5Error("failed to read environment line") from ex
    except csv.Error as ex:
        raise Toa5Error("CSV parse error on environment line") from ex
    if len(env_line)<1 or env_line[0]!='TOA5':
        raise Toa5Error("not a TOA5 file?")
    if len(_env_line_keys) != len(env_line):
        raise Toa5Error("TOA5 environment line length mismatch")
    env_line_dict = dict(zip_strict(_env_line_keys, env_line))
    del env_line_dict['toa5']
    # ### Read the header rows
    try:
        field_names = next(csv_reader)
        units = next(csv_reader)
        proc = next(csv_reader)
    except StopIteration as ex:
        raise Toa5Error("unexpected end of headers") from ex
    except csv.Error as ex:
        raise Toa5Error("CSV parse error on headers") from ex
    # ### Do some checks on the header
    if len(field_names) != len(units) or len(field_names) != len(proc):
        raise Toa5Error("header column count mismatch")
    try:
        set(no_duplicates(field_names, name='column name'))
    except ValueError as ex:
        raise Toa5Error(*ex.args)  # pylint: disable=raise-missing-from  # (we're just stealing the error message)
    columns = tuple( ColumnHeader(*c) for c in zip_strict(field_names, units, proc) )
    return EnvironmentLine(**env_line_dict), columns

def write_header(env_line :EnvironmentLine, columns :Sequence[ColumnHeader]) -> Generator[Sequence[str], None, None]:
    """TODO: Doc"""
    yield ('TOA5',)+env_line
    yield tuple( c.name for c in columns )
    yield tuple( c.unit for c in columns )
    yield tuple( c.prc for c in columns )

def read_pandas(fh, *, col_trans :ColumnHeaderTransformer = default_col_hdr_transform, **kwargs):
    """A helper function to read TOA5 files into a Pandas DataFrame with ``pandas.read_csv``.

    >>> import toa5
    >>> with open('Example.dat', encoding='ASCII', newline='') as fh:
    ...     df = toa5.read_pandas(fh, low_memory=False)
    >>> print(df)  # doctest: +NORMALIZE_WHITESPACE
                RECORD  BattV_Min[V]
    TIMESTAMP                       \n\
    2021-06-19       0         12.99
    2021-06-20       1         12.96
    >>> print(df.attrs['toa5_env_line'])  # doctest: +NORMALIZE_WHITESPACE
    EnvironmentLine(station_name='TestLogger', logger_model='CR1000X', logger_serial='12342',
    logger_os='CR1000X.Std.03.02', program_name='CPU:TestLogger.CR1X', program_sig='2438', table_name='Example')

    :param fh: TODO Doc
    :param col_trans: TODO Doc
    :param kwargs: Additional keyword arguments are passed through to ``pandas.read_csv``.
        Not allowed are ``filepath_or_buffer``, ``header``, and ``names``.
        Other options that this function provides by default, such as ``na_values`` or ``index_col``, may be overridden.
    :return: A Pandas DataFrame.
        The :class:`EnvironmentLine` is stored in the DataFrame's ``attrs`` under the key ``toa5_env_line``.
        Note that, at the time of writing, Pandas documents ``attrs`` as being experimental.
    """
    if any( k in kwargs for k in ('filepath_or_buffer','header','names') ):
        raise KeyError("Arguments 'filepath_or_buffer', 'header', and 'names' may not be used")
    pd = importlib.import_module('pandas')
    env_line, columns = read_header( csv.reader(fh, strict=True) )
    cols = [ col_trans(c) for c in columns ]
    xa = {}
    if columns[0] == ColumnHeader(name='TIMESTAMP', unit='TS'):
        xa['parse_dates'] = [0]
        xa['index_col'] = [0]
    elif columns[0] == ColumnHeader(name='RECORD', unit='RN'):
        xa['index_col'] = [0]
    df = pd.read_csv(fh, header=None, names=cols, na_values=['NAN'], **xa, **kwargs)
    df.attrs['toa5_env_line'] = env_line
    return df
