"""Tests for :mod:`toa5` and :mod:`toa5.to_csv`.

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
import io
import os
import csv
import doctest
import unittest
from pathlib import Path
from functools import partial
from unittest.mock import patch
from typing import Optional, Any
from collections.abc import Callable, Sequence
from contextlib import redirect_stdout, redirect_stderr
from igbpyutils.file import Pushd, NamedTempFileDeleteLater
from pandas.testing import assert_frame_equal
import pandas
import toa5.to_csv
import toa5

_exp_env_daily = toa5.EnvironmentLine(station_name="TestLogger",logger_model="CR1000X",logger_serial="12342",
    logger_os="CR1000X.Std.03.02",program_name="CPU:TestLogger.CR1X",program_sig="2438",table_name="Daily")
_exp_env_hourly = _exp_env_daily._replace(table_name="Hourly")

_exp_hdr :dict[str, tuple[tuple[toa5.ColumnHeader, str, str],...]] = {
    "Daily": (
        # tuples of ColumnHeader, short_name, SQL name (see test_col_trans) for the latter two
        ( toa5.ColumnHeader(name="TIMESTAMP", unit="TS"), "TIMESTAMP", "timestamp" ),
        ( toa5.ColumnHeader(name="RECORD", unit="RN"), "RECORD", "record" ),
        ( toa5.ColumnHeader(name="BattV_Min", unit="Volts", prc="Min"), "BattV_Min[V]", "battv_min" ),
        ( toa5.ColumnHeader(name="BattV_TMn", prc="TMn"), "BattV_TMn", "battv_tmn" ),
        ( toa5.ColumnHeader(name="PTemp", unit="oC", prc="Smp"), "PTemp[°C]", "ptemp" ),
        ( toa5.ColumnHeader(name="PTemp_C_Min", unit="Deg C", prc="Min"), "PTemp_C_Min[°C]", "ptemp_c_min" ),
        ( toa5.ColumnHeader(name="PTemp_C_TMn", prc="TMn"), "PTemp_C_TMn", "ptemp_c_tmn" ),
        ( toa5.ColumnHeader(name="PTemp_C_Max", unit="Deg C", prc="Max"), "PTemp_C_Max[°C]", "ptemp_c_max" ),
        ( toa5.ColumnHeader(name="PTemp_C_TMx", prc="TMx"), "PTemp_C_TMx", "ptemp_c_tmx" ),
    ),
    "Hourly": (
        ( toa5.ColumnHeader(name="TIMESTAMP", unit="TS"), "TIMESTAMP", "timestamp" ),
        ( toa5.ColumnHeader(name="RECORD", unit="RN"), "RECORD", "record" ),
        ( toa5.ColumnHeader(name="BattV", unit="Volts", prc="Avg"), "BattV/Avg[V]", "battv_avg" ),
        ( toa5.ColumnHeader(name="PTemp_C_Min", unit="Deg C", prc="Min"), "PTemp_C_Min[°C]", "ptemp_c_min" ),
        ( toa5.ColumnHeader(name="PTemp_C_Max", unit="Deg C", prc="Max"), "PTemp_C_Max[°C]", "ptemp_c_max" ),
        ( toa5.ColumnHeader(name="AirT_C(42)", unit="Deg C", prc="Smp"), "AirT_C(42)[°C]", "airt_c_42" ),
        ( toa5.ColumnHeader(name="RelHumid_Avg(3)", unit="%", prc="Avg"), "RelHumid_Avg(3)[%]", "relhumid_avg_3" ),
    ),
}

_in_path = Path(__file__).parent/'toa5'

def load_tests(_loader :unittest.TestLoader, tests :unittest.TestSuite, _ignore) -> unittest.TestSuite:
    globs :dict = {}
    def doctest_setup(_t :doctest.DocTest):
        globs['_prev_dir'] = os.getcwd()
        os.chdir( Path(__file__).parent/'doctest_wd' )
    def doctest_teardown(_t :doctest.DocTest):
        os.chdir( globs['_prev_dir'] )
        del globs['_prev_dir']
    tests.addTests(doctest.DocTestSuite(toa5, setUp=doctest_setup, tearDown=doctest_teardown, globs=globs))
    return tests

class Toa5TestCase(unittest.TestCase):

    def test_toa5_read_write_header(self):
        # read header
        with (_in_path/'TestLogger_Daily_1.dat').open(encoding='ASCII', newline='') as fh:
            csv_rd = csv.reader(fh, strict=True)
            env_line, columns = toa5.read_header(csv_rd)
            self.assertEqual(env_line, _exp_env_daily)
            self.assertEqual(columns, tuple( t[0] for t in _exp_hdr['Daily'] ))
        # read header, different file
        with (_in_path/'TestLogger_Hourly_1.dat').open(encoding='ASCII', newline='') as fh:
            csv_rd = csv.reader(fh, strict=True)
            env_line, columns = toa5.read_header(csv_rd)
            self.assertEqual(env_line, _exp_env_hourly)
            self.assertEqual(columns, tuple( t[0] for t in _exp_hdr['Hourly'] ))
        # write header
        self.assertEqual( tuple( toa5.write_header(env_line, columns) ), (
            ("TOA5","TestLogger","CR1000X","12342","CR1000X.Std.03.02","CPU:TestLogger.CR1X","2438","Hourly"),
            ("TIMESTAMP","RECORD","BattV","PTemp_C_Min","PTemp_C_Max","AirT_C(42)","RelHumid_Avg(3)"),
            ("TS","RN","Volts","Deg C","Deg C","Deg C","%"),
            ("","","Avg","Min","Max","Smp","Avg"),
        ) )

    def test_bad_toa5(self):
        # various bad TOA5 files
        for fi in range(1, 13):
            with (_in_path/f'TestLogger_Hourly_Bad{fi:02d}.dat').open(encoding='ASCII', newline='') as fh:
                csv_rd = csv.reader(fh, strict=True)
                with self.assertRaises(toa5.Toa5Error):
                    toa5.read_header(csv_rd)
        # test allow_dupes
        dupe_cols = ( ('TOA5','sn','lm','ls','os','pn','ps','tn'),('Foo','Foo'),('',''),('','') )
        with self.assertRaises(toa5.Toa5Error):
            toa5.read_header(iter(dupe_cols))
        toa5.read_header(iter(dupe_cols), allow_dupes=True)

    def test_col_trans(self):
        # check the transformation functions
        for tp in _exp_hdr.values():
            for ch, cn, sq in tp:
                self.assertEqual(toa5.default_col_hdr_transform(ch), cn)
                self.assertEqual(toa5.sql_col_hdr_transform(ch), sq)
        self.assertEqual(toa5.sql_col_hdr_transform(toa5.ColumnHeader('__Fö-x__Avg(1,2)','xyz','Avg')), 'f_x_avg_1_2')
        # test some claims from the documentation
        self.assertEqual(toa5.default_col_hdr_transform(toa5.ColumnHeader("Test","","Min")),
                         toa5.default_col_hdr_transform(toa5.ColumnHeader("Test/Min","","Smp")) )
        self.assertEqual(toa5.default_col_hdr_transform(toa5.ColumnHeader("Test","","Min")), "Test/Min" )
        self.assertEqual(toa5.sql_col_hdr_transform(toa5.ColumnHeader("Test_1","Volts","")),
                         toa5.sql_col_hdr_transform(toa5.ColumnHeader("Test(1)","","Smp")))
        self.assertEqual(toa5.sql_col_hdr_transform(toa5.ColumnHeader("Test_1","Volts","")), "test_1" )

    def test_pandas(self):
        el = toa5.EnvironmentLine(station_name='sn', logger_model='lm', logger_serial='ls', logger_os='os',
                                  program_name='pn', program_sig='ps', table_name='tn' )
        # basic test (detects RECORD as the Index)
        fh = io.StringIO(
            "TOA5,sn,lm,ls,os,pn,ps,tn\n"
            "RECORD,BattV_Min\n"
            "RN,Volts\n"
            ",Min\n"
            "1,12\n"
            "2,11.9\n")
        df = toa5.read_pandas(fh, low_memory=False)
        assert_frame_equal(df, pandas.DataFrame(
            index=pandas.Index(name='RECORD', data=[1,2]),
            data={ 'BattV_Min[V]': [12,11.9] }  ) )
        self.assertEqual( df.attrs['toa5_env_line'], el )
        # basic test, no auto-detected Index
        fh = io.StringIO(
            "TOA5,sn,lm,ls,os,pn,ps,tn\n"
            "Blah,BattV_Min\n"
            ",Volts\n"
            ",Min\n"
            "1,12\n"
            "2,11.9")
        df = toa5.read_pandas(fh, low_memory=False)
        assert_frame_equal(df, pandas.DataFrame(
            index=pandas.Index(data=[0,1]),
            data={ 'Blah':[1,2], 'BattV_Min[V]':[12,11.9] } ) )
        self.assertEqual( df.attrs['toa5_env_line'], el )
        # test overriding `index_col`
        fh = io.StringIO(
            "TOA5,sn,lm,ls,os,pn,ps,tn\n"
            "RECORD,Foo\n"
            "RN,\n"
            ",\n"
            "1,3\n"
            "2,4\n")
        df = toa5.read_pandas(fh, index_col=[1], low_memory=False)
        assert_frame_equal(df, pandas.DataFrame(
            index=pandas.Index(name='Foo', data=[3,4]),
            data={ 'RECORD': [1,2] }  ) )
        self.assertEqual( df.attrs['toa5_env_line'], el )
        # test overriding `names`
        fh = io.StringIO(
            "TOA5,sn,lm,ls,os,pn,ps,tn\n"
            "RECORD,Foo\n"
            "RN,\n"
            ",\n"
            "1,3\n"
            "2,4\n")
        df = toa5.read_pandas(fh, names=["xyz","abc"], low_memory=False)
        assert_frame_equal(df, pandas.DataFrame(
            index=pandas.Index(name='xyz', data=[1,2]),
            data={ 'abc': [3,4] }  ) )
        self.assertEqual( df.attrs['toa5_env_line'], el )
        # test reading from file instead of handle
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\n"
                b"RECORD,BattV_Min\n"
                b"RN,Volts\n"
                b",Min\n"
                b"5,13.1\n"
                b"6,12.9\n")
            tf.close()
            df = toa5.read_pandas(tf.name, low_memory=False)
        assert_frame_equal(df, pandas.DataFrame(
            index=pandas.Index(name='RECORD', data=[5,6]),
            data={ 'BattV_Min[V]': [13.1,12.9] }  ) )
        self.assertEqual( df.attrs['toa5_env_line'], el )

    def test_to_csv_cli(self):
        with Pushd(Path(__file__).parent/'doctest_wd'):
            # basic test
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-t','Example.dat'])), [
                'TIMESTAMP,RECORD,BattV_Min[V]',
                '2021-06-19 00:00:00,0,12.99',
                '2021-06-20 00:00:00,1,12.96',
            ] )
            # basic test with env line as JSON and --simple-names
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-l-','-nt','Example.dat'])), [
                'TIMESTAMP,RECORD,BattV_Min',
                '2021-06-19 00:00:00,0,12.99',
                '2021-06-20 00:00:00,1,12.96',
                '{',
                '  "station_name": "TestLogger",',
                '  "logger_model": "CR1000X",',
                '  "logger_serial": "12342",',
                '  "logger_os": "CR1000X.Std.03.02",',
                '  "program_name": "CPU:TestLogger.CR1X",',
                '  "program_sig": "2438",',
                '  "table_name": "Example"',
                '}'
            ] )
            # --sql-names
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-ts','Example.dat'])), [
                'timestamp,record,battv_min',
                '2021-06-19 00:00:00,0,12.99',
                '2021-06-20 00:00:00,1,12.96',
            ] )
        # test errors
        self._fake_cli(partial(toa5.to_csv.main,['-eLatin1']), stderr=None,
            exit_call=(2, 'toa5.to_csv: error: Can only use --in-encoding when specifying an input file\n'))
        self._fake_cli(partial(toa5.to_csv.main,['-cLatin1']), stderr=None,
            exit_call=(2, 'toa5.to_csv: error: Can only use --out-encoding when specifying an output file\n'))
        self._fake_cli(partial(toa5.to_csv.main,['-ns']), stderr=None,
            exit_call=(2, "toa5.to_csv: error: Can't use --sql-names and --simple-names together\n"))
        # just for coverage: a test with no data
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\nRECORD,BattV_Min\nRN,Volts\n,Min")
            tf.close()
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,[tf.name])), ['RECORD,BattV_Min[V]'] )
        # test --require-timestamp
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\nRECORD,BattV_Min\nRN,Volts\n,Min\n1,12\n")
            tf.close()
            with self.assertRaises(ValueError):
                self._fake_cli(partial(toa5.to_csv.main,['-t',tf.name]))
        # test --allow-jagged
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\nTIMESTAMP,RECORD,BattV_Min\nTS,RN,Volts\n,,Min\n\"2021-06-19 00:00:00\",1")
            tf.close()
            with self.assertRaises(ValueError):
                self._fake_cli(partial(toa5.to_csv.main,[tf.name]))
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-j',tf.name])), [
                "TIMESTAMP,RECORD,BattV_Min[V]", "2021-06-19 00:00:00,1" ] )
        # --allow-dupes
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\nFoo,Foo\n,\nSmp,Min")
            tf.close()
            with self.assertRaises(toa5.Toa5Error):
                self._fake_cli(partial(toa5.to_csv.main,[tf.name]))
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-a',tf.name])), ["Foo,Foo/Min"] )
        # test with dupe column names after transform
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\nxy/Min,xy\n,\nSmp,Min")
            tf.close()
            with self.assertRaises(ValueError):
                self._fake_cli(partial(toa5.to_csv.main,[tf.name]))
            # --allow-dupes
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-a',tf.name])), ["xy/Min,xy/Min"] )
            # not a dupe with --simple--names
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-n',tf.name])), ["xy/Min,xy"] )
        # test --sql-names with dupes
        with NamedTempFileDeleteLater() as tf:
            tf.write(b"TOA5,sn,lm,ls,os,pn,ps,tn\nx-y.min,x--y\n,\n,Min")
            tf.close()
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,[tf.name])), ["x-y.min,x--y/Min"] )
            with self.assertRaises(ValueError):
                self._fake_cli(partial(toa5.to_csv.main,['-s',tf.name]))
            # --allow-dupes
            self.assertEqual( self._fake_cli(partial(toa5.to_csv.main,['-sa',tf.name])), ["x_y_min,x_y_min"] )

    def _fake_cli(self, main :Callable[[], None], *,
                  exit_call :Sequence[Any] = (0,), stderr :Optional[str] = '' ) -> list[str]:
        with (redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err,
              patch('argparse.ArgumentParser.exit', side_effect=SystemExit) as mock_exit):
            try:
                main()
            except SystemExit:
                pass
        mock_exit.assert_called_once_with(*exit_call)
        if stderr is not None:
            self.assertEqual(err.getvalue(), stderr)
        return out.getvalue().splitlines()
