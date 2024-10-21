
.. include:: ../README.rst
   :end-before: **The documentation is available at** https://haukex.github.io/pytoa5/

[ `Source code on GitHub <https://github.com/haukex/pytoa5>`_
| `Author, Copyright, and License`_ ]

TL;DR
-----

- Code examples with :mod:`csv`: :func:`toa5.read_header`
- Code example with :mod:`pandas`: :func:`toa5.read_pandas`
- `Command-Line TOA5-to-CSV Tool`_

Documentation
-------------
[ :ref:`genindex` ]

.. automodule:: toa5

.. automodule:: toa5.to_csv

.. toa5_to_csv_cli_doc::

Changelog
---------

v0.9.2 - 2024-10-21
^^^^^^^^^^^^^^^^^^^

- Added :meth:`toa5.ColumnHeader.simple_checks`
- **Potentially incompatible changes:**
- Added ``strict`` to :func:`toa5.default_col_hdr_transform` and enabled it by
  default, so the characters ``/[]`` are now not allowed in column names
- :func:`toa5.default_col_hdr_transform` now strips whitespace
- :func:`toa5.default_col_hdr_transform` and :func:`toa5.sql_col_hdr_transform`
  now no longer drop "Smp" from :attr:`toa5.ColumnHeader.prc`
- Therefore, temporarily marked this project as "Beta"

v0.9.1 - 2024-10-19
^^^^^^^^^^^^^^^^^^^

- Actually allow overriding :func:`toa5.read_pandas` arguments (didn't work as documented)
- Made :func:`toa5.read_pandas` arguments more flexible: accept filename as well,
  and allow overriding all arguments.
- Added ``--sql-names`` and ``--allow-dupes`` to CLI
- A few documentation updates.

v0.9.0 - 2024-10-18
^^^^^^^^^^^^^^^^^^^

- Initial release

.. include:: ../README.rst
    :start-after: **The documentation is available at** https://haukex.github.io/pytoa5/
