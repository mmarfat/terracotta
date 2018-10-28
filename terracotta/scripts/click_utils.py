"""scripts/click_utils.py

Custom click parameter types and utilities.
"""

from typing import List, Any, Tuple, Dict
import pathlib
import glob
import re
import os
import string

import click


class GlobbityGlob(click.ParamType):
    """Expands a glob pattern to Path objects"""
    name = 'glob'

    def convert(self, value: str, *args: Any) -> List[pathlib.Path]:
        return [pathlib.Path(f) for f in glob.glob(value)]


class PathlibPath(click.Path):
    """Converts a string to a pathlib.Path object"""

    def convert(self, *args: Any) -> pathlib.Path:  # type: ignore
        return pathlib.Path(super().convert(*args))


RasterPatternType = Tuple[List[str], Dict[Tuple[str, ...], str]]


class RasterPattern(click.ParamType):
    """Expands a pattern following the Python format specification to matching files"""
    name = 'raster-pattern'

    def convert(self, value: str, *args: Any) -> RasterPatternType:
        value = os.path.realpath(value)

        try:
            parsed_value = list(string.Formatter().parse(value))
        except ValueError as exc:
            self.fail(f'Invalid pattern: {exc!s}')

        # extract keys from format string and assemble glob and regex patterns matching it
        keys = []
        glob_pattern = ''
        regex_pattern = ''
        for before_field, field_name, _, _ in parsed_value:
            glob_pattern += before_field
            regex_pattern += re.escape(before_field)
            if field_name is None:  # no placeholder
                continue
            glob_pattern += '*'
            if field_name == '':  # unnamed placeholder
                regex_pattern += '.*?'
            elif field_name in keys:  # duplicate placeholder
                key_group_number = keys.index(field_name) + 1
                regex_pattern += f'\\{key_group_number}'
            else:  # new placeholder
                keys.append(field_name)
                regex_pattern += f'(?P<{field_name}>[^\\W_]+)'

        if not keys:
            self.fail('Pattern must contain at least one placeholder')

        if not all(re.match(r'\w', key) for key in keys):
            self.fail('Key names must be alphanumeric')

        # use glob to find candidates, regex to extract placeholder values
        candidates = map(os.path.realpath, glob.glob(glob_pattern))
        matched_candidates = [re.match(regex_pattern, candidate) for candidate in candidates]

        if not any(matched_candidates):
            self.fail('Given pattern matches no files')

        key_combinations = [tuple(match.groups()) for match in matched_candidates if match]
        if len(key_combinations) != len(set(key_combinations)):
            self.fail('Pattern leads to duplicate keys')

        files = {tuple(match.groups()): match.group(0) for match in matched_candidates if match}
        return keys, files


class TOMLFile(click.ParamType):
    """Parses a TOML file to a dict"""
    name = 'toml-file'

    def convert(self, value: str, *args: Any) -> Dict[str, Any]:
        import toml
        return dict(toml.load(value))


class Hostname(click.ParamType):
    """Parses a string to a valid hostname"""
    name = 'url'

    def __init__(self, default_port: int = 5000, default_scheme: str = 'http') -> None:
        self.default_port = default_port
        self.default_scheme = default_scheme

    def convert(self, value: str, *args: Any) -> str:
        from urllib.parse import urlparse, urlunparse
        parsed_url = urlparse(value)

        if not parsed_url.netloc:
            value_with_scheme = '://'.join([self.default_scheme, value])
            parsed_url = urlparse(value_with_scheme)

        # remove everything we don't need
        return urlunparse([parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''])
