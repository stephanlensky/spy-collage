import asyncio
from typing import Any, Callable, Optional

import typer


def run_until_complete_with_progress(
    tasks: list,
    label: Optional[str] = None,
    length: Optional[int] = None,
    transform_result: Optional[Callable] = None,
    unpack_result: bool = False,
):
    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(task) for task in tasks]
    if length is None:
        length = len(tasks)

    async def run_and_wait_with_progress() -> list:
        results: list[Any] = []
        with typer.progressbar(
            length=length,
            label=label,
            show_pos=True,
        ) as progress:
            for t in tasks:
                result = await t
                if transform_result:
                    result = transform_result(result)

                if unpack_result:
                    results.extend(result)
                    progress.update(len(result))
                else:
                    results.append(result)
                    progress.update(1)

        return results

    return loop.run_until_complete(run_and_wait_with_progress())
