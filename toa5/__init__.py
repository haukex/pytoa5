"""
TOA5 files are essentially CSV files that have four header rows:

1. The "environment line": :class:`EnvironmentLine`
2. The column header names: :attr:`ColumnHeader.name`
3. The columns' units: :attr:`ColumnHeader.unit`
4. The columns' "data process": :attr:`ColumnHeader.prc`

The following two functions can be used to read files with this header:

.. autofunction:: read_header

.. autofunction:: read_pandas

.. autoclass:: EnvironmentLine
    :members:
    :undoc-members:

.. autoclass:: ColumnHeader
    :members:

.. autofunction:: write_header

.. autoclass:: ColumnHeaderTransformer

.. autofunction:: default_col_hdr_transform

.. autofunction:: short_name

.. autodata:: SHORTER_UNITS
    :no-value:

.. autofunction:: sql_col_hdr_transform

.. autoexception:: Toa5Error

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
import os
import re
import csv
import warnings
import importlib
from contextlib import nullcontext
from typing import NamedTuple, Optional, Any
from collections.abc import Iterator, Sequence, Generator, Callable
from igbpyutils.iter import no_duplicates, zip_strict

class Toa5Error(RuntimeError):
    """An error class for :func:`read_header`."""

class Toa5Warning(UserWarning):
    """A generic warning class for warnings from this module."""

class EnvironmentLine(NamedTuple):
    """Named tuple representing a TOA5 "Environment Line", giving details about the data logger and its program."""
    #: Station (data logger) name
    station_name :str
    #: Model number of the data logger
    logger_model :str
    #: Serial number of the data logger
    logger_serial :str
    #: Data logger operating system and version
    logger_os :str
    #: The name of the program on the data logger
    program_name :str
    #: The program's signature (checksum)
    program_sig :str
    #: The name of the table contained in this TOA5 file
    table_name :str

_col_name_re = re.compile(r'\A[A-Za-z_$][A-Za-z0-9_$]*(?:\([0-9]+(?:,[0-9]+)*\))?\Z')
_col_unit_re = re.compile(r'\A['
    + bytes(range(0x20, 0x7F)).decode('ASCII')
    .replace("\\",'').replace('-',r'\-').replace(']',r'\]')
    .replace(bytes(range(ord('A'),ord('Z')+1)).decode('ASCII'), 'A-Z')
    .replace(bytes(range(ord('a'),ord('z')+1)).decode('ASCII'), 'a-z')
    .replace(bytes(range(ord('0'),ord('9')+1)).decode('ASCII'), '0-9')
    + r'°]{0,64}\Z')
_col_prc_re = re.compile(r'\A[A-Za-z0-9_-]{0,32}\Z')

class ColumnHeader(NamedTuple):
    """Named tuple representing a column header.

    This class represents a column header as it would be read from a text (CSV) file, therefore,
    when optional fields are empty, this is represented by empty strings, not by ``None``.
    """
    #: Column name.
    name :str
    #: Scientific/engineering units (optional)
    unit :str = ""
    #: "Data process" (optional; examples:  ``"Smp"``, ``"Avg"``, ``"Max"``, etc.)
    prc :str = ""

    def simple_checks(self, *, strict :bool = True) -> str:
        """Validates the values in this object against some rules mostly derived from experience:

        - :attr:`name` must start with letters, an underscore, or dollar sign,
          and otherwise only consist of letters, numbers, underscores, and dollar sign,
          optionally followed by indices (integers separated by commas) in parentheses.
          May not be longer than 255 characters in total.
        - :attr:`unit` is fairly lenient and currently allows most printable ASCII
          characters except backslash. May not be longer than 64 characters in total.
        - :attr:`prc` is fairly strict and currently allows only up to 32 letters, numbers,
          underscores, and dashes.

        .. important::
            Since these rules are derived from experience, they may be adapted in the future,
            and they may not accurately reflect the rules your data logger imposes on the values.
            This should normally not be a problem, because within this library, this function
            is currently only used to generate warnings in :func:`default_col_hdr_transform`,
            and you are free to disable its ``strict`` option.

            Please feel free to `suggest changes <https://github.com/haukex/pytoa5/issues>`_.

        :param strict: Whether or not to raise an error for invalid values.
        :return: Returns the empty string if there are no problems. When ``strict`` is off
            and problems are detected, returns a string describing the problems.
        :raises ValueError: When ``strict`` is on and any unusual values are detected.
        """
        problems :list[str] = []
        if len(self.name)>255 or not _col_name_re.fullmatch(self.name):
            problems.append(f"column name {self.name!r}")
        if not _col_unit_re.fullmatch(self.unit):
            problems.append(f"unit {self.unit!r}")
        if not _col_prc_re.fullmatch(self.prc):
            problems.append(f"data process {self.prc}")
        if strict and problems:
            raise ValueError(f"Unexpected {', '.join(problems)}")
        return f"Unusual {', '.join(problems)}" if problems else ''

#: A type for a function that takes a :class:`ColumnHeader` and turns it into a single string. See :func:`default_col_hdr_transform`.
ColumnHeaderTransformer = Callable[[ColumnHeader], str]

#: A table of shorter versions of common units, used in :func:`default_col_hdr_transform`.
SHORTER_UNITS :dict[str, str] = {
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
    """Append the :attr:`~ColumnHeader.prc` if it's not already present at the end of the :attr:`~ColumnHeader.name`."""
    if col.prc and not re.search(re.escape(col.prc)+r'(?:\([^)]*\))?\Z', col.name, re.I):
        return col.name.strip() + sep + col.prc.strip()
    return col.name.strip()

_sql_trans_re = re.compile(r'[^A-Za-z_0-9]+')
_sql_under_re = re.compile(r'_{2,}')
def sql_col_hdr_transform(col :ColumnHeader) -> str:
    """An alternative function that transforms a :class:`ColumnHeader` to a string suitable for use in SQL.

    - appends :attr:`ColumnHeader.prc` (unless the name already ends with it)
    - any characters that are not ASCII letters or numbers are converted to underscores
      (and consecutive underscores are reduced to a single one)
    - the returned name is all-lowercase
    - units are omitted (these could be stored in an SQL column comment, for example)

    .. warning::
        This transformation can potentially result in two columns on the same table
        having the same name, for example, this would be the case with
        ``ColumnHeader("Test_1","Volts","Smp")`` and ``ColumnHeader("Test(1)","","Smp")``,
        which would both result in ``"test_1_smp"``.

        Therefore, it is **strongly recommended** that you check for duplicate
        column names after using this transformer. For example, see
        :func:`more_itertools.classify_unique`.

    :param col: The :class:`ColumnHeader` to process.
    """
    return _sql_under_re.sub('_', _sql_trans_re.sub('_', _maybe_prc(col, '_'))).strip('_').lower()

def default_col_hdr_transform(col :ColumnHeader, *, short_units :Optional[dict[str,str]] = None, strict :bool = True) -> str:
    """The default function used to transform a :class:`ColumnHeader` into a single string.

    This conversion is slightly opinionated and will:

    - strip all whitespace from :class:`ColumnHeader` values,
    - append :attr:`ColumnHeader.prc` to the name with a slash (unless the name already ends with it),
    - append the units in square brackets shorten some units, and
    - ignore the "TS" and "RN" units on the "TIMESTAMP" and "RECORD" columns, respectively.

    :param col: The :class:`ColumnHeader` to process.
    :param short_units: A lookup table in which the keys are the original unit names as
        they appear in the TOA5 file, and the values are a shorter version of that unit.
        If not provided, defaults to :data:`SHORTER_UNITS`.
    :param strict: When this is enabled (the default), raise a :exc:`ValueError` if the
        column name contains the characters ``/[]``, which might cause duplicate column
        names in a table, and warn if :meth:`ColumnHeader.simple_checks` fails.
    """
    if short_units is None:  # pragma: no branch
        short_units = SHORTER_UNITS
    if strict and any( x in col.name for x in '/[]' ):
        raise ValueError(f"Column name {col.name!r} may not contain any of '/[]'")
    if strict and (w := col.simple_checks(strict=False)):
        warnings.warn(w, Toa5Warning)
    c = _maybe_prc(col, '/')
    if col.unit and \
            not ( col.name=='TIMESTAMP' and col.unit=='TS' or col.name=='RECORD' and col.unit=='RN' ) \
            and len(short_units.get(col.unit, col.unit)):
        c += "[" + short_units.get(col.unit, col.unit).strip() + "]"
    return c

#: A short alias for :func:`default_col_hdr_transform`.
short_name = default_col_hdr_transform

_env_line_keys = ('toa5',) + EnvironmentLine._fields
def read_header(csv_reader :Iterator[Sequence[str]], *, allow_dupes :bool = False) -> tuple[EnvironmentLine, tuple[ColumnHeader, ...]]:
    """Read the header of a TOA5 file.

    A common use case to read a TOA5 file would be the following; as you can see, the main difference
    between reading a regular CSV file and a TOA5 file is the additional call to this function.

    >>> import csv, toa5
    >>> with open('Example.dat', encoding='ASCII', newline='') as fh:
    ...     csv_rd = csv.reader(fh, strict=True)
    ...     env_line, columns = toa5.read_header(csv_rd)
    ...     print([ toa5.short_name(col) for col in columns ])
    ...     for row in csv_rd:
    ...         print(row)
    ['TIMESTAMP', 'RECORD', 'BattV_Min[V]']
    ['2021-06-19 00:00:00', '0', '12.99']
    ['2021-06-20 00:00:00', '1', '12.96']

    This also works with :class:`csv.DictReader`:

    >>> import csv, toa5
    >>> with open('Example.dat', encoding='ASCII', newline='') as fh:
    ...     env_line, columns = toa5.read_header(csv.reader(fh, strict=True))
    ...     for row in csv.DictReader(fh, strict=True,
    ...             fieldnames=[toa5.short_name(col) for col in columns]):
    ...         print(row)
    {'TIMESTAMP': '2021-06-19 00:00:00', 'RECORD': '0', 'BattV_Min[V]': '12.99'}
    {'TIMESTAMP': '2021-06-20 00:00:00', 'RECORD': '1', 'BattV_Min[V]': '12.96'}

    :seealso: :func:`short_name`, used in the examples above, is an alias for
        :func:`default_col_hdr_transform`.

    :param csv_reader: The :func:`csv.reader` object to read the header rows from. Only the header is read from the file,
        so after you call this function, you can use the reader to read the data rows from the input file.
    :param allow_dupes: Whether or not to allow duplicates in the :attr:`ColumnHeader.name` values.
    :return: Returns an :class:`EnvironmentLine` object and a tuple of :class:`ColumnHeader` objects.
    :raises Toa5Error: In case any error is encountered while reading the TOA5 header.
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
    if not allow_dupes:
        try:
            set(no_duplicates(field_names, name='column name'))
        except ValueError as ex:
            raise Toa5Error(*ex.args)  # pylint: disable=raise-missing-from  # (we're just stealing the error message)
    columns = tuple( ColumnHeader(*c) for c in zip_strict(field_names, units, proc) )
    return EnvironmentLine(**env_line_dict), columns

def write_header(env_line :EnvironmentLine, columns :Sequence[ColumnHeader]) -> Generator[Sequence[str], None, None]:
    """Convert an :class:`EnvironmentLine` and sequence of :class:`ColumnHeader` objects back
    into the four TOA5 header rows, suitable for use in e.g. :meth:`~csv.csvwriter.writerows`."""
    yield ('TOA5',)+env_line
    yield tuple( c.name for c in columns )
    yield tuple( c.unit for c in columns )
    yield tuple( c.prc for c in columns )

def read_pandas(filepath_or_buffer, *, encoding :str = 'UTF-8', encoding_errors :str = 'strict',
                col_trans :ColumnHeaderTransformer = default_col_hdr_transform, **kwargs):
    """A helper function to read TOA5 files into a :class:`pandas.DataFrame`.
    Uses :func:`read_header` and :func:`pandas.read_csv` internally.

    >>> import toa5, pandas
    >>> df = toa5.read_pandas('Example.dat', low_memory=False)
    >>> print(df)  # doctest: +NORMALIZE_WHITESPACE
                RECORD  BattV_Min[V]
    TIMESTAMP                       \n\
    2021-06-19       0         12.99
    2021-06-20       1         12.96
    >>> print(df.attrs['toa5_env_line'])  # doctest: +NORMALIZE_WHITESPACE
    EnvironmentLine(station_name='TestLogger', logger_model='CR1000X',
        logger_serial='12342', logger_os='CR1000X.Std.03.02',
        program_name='CPU:TestLogger.CR1X', program_sig='2438',
        table_name='Example')

    :param filepath_or_buffer: A filename or file object from which to read the TOA5 data.

        .. note::
            Unlike :func:`pandas.read_csv`, URLs are not accepted, only such filenames that Python's :func:`open` accepts.

    :param col_trans: The :class:`ColumnHeaderTransformer` to use to convert the :class:`ColumnHeader` objects
        into column names. Defaults to :func:`default_col_hdr_transform`
    :param kwargs: Any additional keyword arguments are passed through to :func:`pandas.read_csv`.
        It is **not recommended** to set ``header`` and ``names``, since they are provided by this function.
        Other options that this function provides by default, such as ``na_values`` or ``index_col``, may be overridden.
    :return: A :class:`pandas.DataFrame`.
        The :class:`EnvironmentLine` is stored in :attr:`pandas.DataFrame.attrs` under the key ``"toa5_env_line"``.

        .. note::
            At the time of writing, :attr:`pandas.DataFrame.attrs` is documented as being experimental.
    """
    pd = importlib.import_module('pandas')
    cm :Any
    if isinstance(filepath_or_buffer, (str, os.PathLike)):
        cm = open(filepath_or_buffer, encoding=encoding, errors=encoding_errors, newline='')
    else:
        cm = nullcontext(filepath_or_buffer)
    with cm as fh:
        env_line, columns = read_header( csv.reader(fh, strict=True) )
        # Note Pandas doesn't allow dupes in `names`, so we should be ok here:
        args :dict[str, Any] = { 'header':None, 'names':[ col_trans(c) for c in columns ], 'na_values':['NAN'] }
        if columns[0] == ColumnHeader(name='TIMESTAMP', unit='TS'):
            args['parse_dates'] = [0]
            args['index_col'] = [0]
        elif columns[0] == ColumnHeader(name='RECORD', unit='RN'):
            args['index_col'] = [0]
        args.update(kwargs)
        df = pd.read_csv(filepath_or_buffer=fh, encoding=encoding, encoding_errors=encoding_errors, **args)
        df.attrs['toa5_env_line'] = env_line
    return df
