import typer


def format_error(msg: str) -> str:
    return f"{typer.style('error', fg=typer.colors.RED, bold=True)}: {msg}"
