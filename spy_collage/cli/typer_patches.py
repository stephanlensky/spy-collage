from typing import Any, Callable, Optional, Type

import click
import typer

_REGISTERED_TYPES: dict[Type, Callable] = {}


class _TyperCustomParam(click.ParamType):
    name = "CustomParameter"

    def __init__(self, typ: type, deserializer: Optional[Callable] = None):
        self.name = typ.__name__
        self._deserializer = typ if deserializer is None else deserializer

    def convert(self, value, param, ctx):
        try:
            return self._deserializer(value)
        except click.BadParameter:
            raise
        except Exception as E:
            raise click.BadParameter(
                f"couldn't serialize {value} to an instance of type {self.name}, error: {E}"
            )


def patch_typer_support_custom_types():
    _get_click_type = typer.main.get_click_type

    def supersede_get_click_type(
        *, annotation: Any, parameter_info: typer.main.ParameterInfo
    ) -> click.ParamType:
        if annotation in _REGISTERED_TYPES:
            return _TyperCustomParam(annotation, _REGISTERED_TYPES[annotation])
        else:
            return _get_click_type(annotation=annotation, parameter_info=parameter_info)

    typer.main.get_click_type = supersede_get_click_type


def register_type(typ: type, deserializer: Callable):
    _REGISTERED_TYPES[typ] = deserializer
