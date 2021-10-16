import re
from dataclasses import dataclass
from pathlib import Path

import click
import spotify_uri

from spy_collage.config import Config
from spy_collage.spotify import collect_albums, get_sp


@dataclass
class AlbumSource:
    source_uris: list[str]

    def albums(self, sp) -> list[dict]:
        return collect_albums(sp, self.source_uris)


class AlbumSourceParam(click.ParamType):
    name = "source"

    def convert(self, value, _param, _ctx) -> AlbumSource:
        if isinstance(value, AlbumSource):
            return value
        elif Path(value).is_file():
            return self.__handle_file_source(value)
        else:
            return self.__handle_uri_source(value)

    def __handle_file_source(self, value) -> AlbumSource:
        uris: set[str] = set()
        with open(value, encoding="utf-8") as f:
            source_str = f.read()
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


@click.command()
@click.pass_context
@click.option(
    "-s",
    "--source",
    required=True,
    type=AlbumSourceParam(),
    help=(
        "A playlist URI, list of comma-separated playlist URIs, or file containing a list of URIs"
        " to generate the collage from"
    ),
)
@click.option(
    "--market",
    default="US",
    show_default=True,
    type=str,
    help="When discovering albums, only consider those available in this market",
)
def cli(ctx, **_kwargs):
    """Configurable Python album art collage generator for Spotify, featuring album discovery and
    color clustering."""
    Config.init(ctx)
    sp = get_sp()
    albums = Config.get("source").albums(sp)
    for album in albums:
        print(f"{album['artists'][0]['name']} - {album['name']}")
