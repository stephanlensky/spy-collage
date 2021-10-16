import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import click
import spotify_uri

from spy_collage.config import Config
from spy_collage.spotify import collect_albums, download_cover, get_sp


class AlbumCoverResolution(Enum):
    small = "small"
    medium = "medium"
    large = "large"


@dataclass
class AlbumSource:
    source_uris: list[str]

    def albums(self, sp) -> list[dict]:
        return collect_albums(sp, self.source_uris, discovery_enabled=Config.get("discover"))


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
    "--discover/--no-discover",
    default=True,
    show_default=True,
    help="Enable/disable automatic album discovery for singles",
)
@click.option(
    "--market",
    default="US",
    show_default=True,
    type=str,
    help="When discovering albums, only consider those available in this market",
)
@click.option(
    "--save-album-uris",
    "save_albums",
    is_flag=True,
    default=False,
    help="Save processed album URIs to albums.txt",
)
@click.option(
    "--album-cover-resolution",
    "album_cover_resolution",
    type=click.Choice([r.value for r in AlbumCoverResolution]),
    default="medium",
    callback=lambda c, p, v: getattr(AlbumCoverResolution, v) if v else None,
    help="Resolution to download album covers at",
)
@click.option(
    "--album-cover-dir",
    "album_cover_dir",
    type=click.Path(),
    default="albums",
    show_default=True,
    help="Location to save cached album covers",
)
def cli(ctx, **_kwargs):
    """Configurable Python album art collage generator for Spotify, featuring album discovery and
    color clustering."""
    Config.init(ctx)
    sp = get_sp()
    albums = Config.get("source").albums(sp)

    if Config.get("save_albums"):
        with open("albums.txt", "w", encoding="utf-8") as of:
            of.writelines([a["uri"] + "\n" for a in albums])

    album_cover_dir = Path(Config.get("album_cover_dir"))
    album_cover_dir.mkdir(exist_ok=True)
    for i, album in enumerate(albums):
        cover_path = album_cover_dir / Path(f"{album['id']}.jpg")
        print(f"Saving cover {i+1}/{len(albums)}", end="\r")
        if not cover_path.exists():
            download_cover(album, cover_path)
    print()

    # frequency: dict[str, int] = {}
    # for album in albums:
    #     s = f"{album['artists'][0]['name']} - {album['name']}"
    #     if s in frequency:
    #         frequency[s] += 1
    #     else:
    #         frequency[s] = 1

    # for k, v in sorted(frequency.items(), key=lambda p: p[1]):
    #     print(k, v)
