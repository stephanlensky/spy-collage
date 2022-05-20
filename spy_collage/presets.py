import json
import re
from ast import literal_eval
from configparser import ConfigParser, ParsingError
from json import JSONDecodeError
from pathlib import Path
from typing import Union

import typer

from spy_collage.cli import format_error
from spy_collage.color_problem import KeyObject, mkline, mkpoint, mkspectrum

PRESETS_PATH = Path("presets.ini")


def load_preset(preset_name: str, width: int, height: int) -> list[KeyObject]:
    config = ConfigParser()
    try:
        config.read(PRESETS_PATH, encoding="utf-8")
    except ParsingError:
        typer.echo(format_error("could not parse presets.ini file"))
        raise typer.Abort()

    try:
        preset = config[preset_name]
    except KeyError:
        typer.echo(
            format_error(f"preset {preset_name} not found. available presets: {config.sections()}")
        )
        raise typer.Abort()

    try:
        key_object_directives = json.loads(preset["key_objects"])
    except KeyError:
        typer.echo(format_error(f"preset {preset_name} does not contain a key_objects field!"))
        raise typer.Abort()
    except JSONDecodeError:
        typer.echo(format_error("could not parse key_objects: value must be a list"))
        raise typer.Abort()

    if not isinstance(key_object_directives, list) or any(
        not isinstance(v, str) for v in key_object_directives
    ):
        typer.echo(format_error("could not parse key_objects: value must be a list of strings"))
        raise typer.Abort()

    key_objects: list[KeyObject] = []
    for directive in key_object_directives:
        try:
            parsed = parse_directive(directive, width, height)
        except ValueError as e:
            typer.echo(format_error(f"could not parse directive: {str(e)}"))
            raise typer.Abort()
        if isinstance(parsed, list):
            key_objects.extend(parsed)
        else:
            key_objects.append(parsed)
    return key_objects


def parse_directive(directive: str, width: int, height: int) -> Union[KeyObject, list[KeyObject]]:
    m = re.match(r"([a-zA-Z]+)\(([^\)]*)\)", directive)
    if m is None:
        raise ValueError("invalid directive format")
    directive_name, raw_args = m.group(1, 2)
    args = [literal_eval(arg.strip()) for arg in raw_args.split(",")]

    if directive_name == "point":
        return mkpoint(*args, width=width, height=height)
    elif directive_name == "line":
        return mkline(*args, width=width, height=height)
    elif directive_name == "spectrum":
        return mkspectrum(*args, width=width, height=height)  # type: ignore
    else:
        raise ValueError(f"invalid directive {directive_name}")
