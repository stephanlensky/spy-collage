import json
import re
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Optional

import click
import spotify_uri


@dataclass
class AlbumSource:
    uris: list[str]
    json_albums: Optional[list[dict[str, Any]]] = None


class AlbumSourceParam(click.ParamType):
    name = "source"

    def convert(self, value, param=None, ctx=None) -> AlbumSource:
        if isinstance(value, AlbumSource):
            return value
        elif Path(value).is_file():
            return self.__handle_file_source(value)
        else:
            return self.__handle_uri_source(value)

    def __handle_file_source(self, value) -> AlbumSource:
        with open(value, encoding="utf-8") as f:
            source_str = f.read()

        try:
            albums = json.loads(source_str)
            return AlbumSource([a["uri"] for a in albums], json_albums=albums)
        except JSONDecodeError:
            pass

        uris: set[str] = set()
        source_uris = re.split(r",\s*|\n", source_str)

        for uri in source_uris:
            uri = uri.strip()
            if not uri:
                continue
            try:
                if uri not in uris:
                    _parsed = spotify_uri.parse(uri)
                    uris.add(uri)
            except Exception:
                self.fail("source file must contain one or more URIs")
        if not uris:
            self.fail("source file must contain one or more URIs")

        return AlbumSource(list(uris))

    def __handle_uri_source(self, value) -> AlbumSource:
        uris: set[str] = set()
        source_uris = value.split(",")

        for uri in source_uris:
            uri = uri.strip()
            if not uri:
                continue
            try:
                if uri not in uris:
                    parsed = spotify_uri.parse(uri)
                    if parsed.type != "playlist":
                        raise TypeError
                    uris.add(uri)
            except Exception:
                self.fail("source must be one or more playlist URIs or a file")

        return AlbumSource(list(uris))
