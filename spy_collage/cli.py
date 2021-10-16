import json
import re
from dataclasses import dataclass
from enum import Enum
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Any, Optional

import click
import spotify_uri

from spy_collage import collage
from spy_collage.config import Config
from spy_collage.spotify import collect_albums, download_cover, get_sp


class AlbumCoverResolution(Enum):
    small = "small"
    medium = "medium"
    large = "large"


@dataclass
class AlbumSource:
    source_uris: list[str]
    cached_albums: Optional[list[dict[str, Any]]] = None

    def albums(self, sp) -> list[dict]:
        if self.cached_albums:
            return self.cached_albums
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
        with open(value, encoding="utf-8") as f:
            source_str = f.read()

        try:
            albums = json.loads(source_str)
            return AlbumSource([a["uri"] for a in albums], cached_albums=albums)
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
    "--save-album-cache",
    "save_albums_cache",
    is_flag=True,
    default=False,
    help="Save full content of Spotify albums API responses to .albums_cache",
)
@click.option(
    "-r",
    "--album-cover-resolution",
    "album_cover_resolution",
    type=click.Choice([r.value for r in AlbumCoverResolution]),
    default="medium",
    callback=lambda c, p, v: getattr(AlbumCoverResolution, v) if v else None,
    help="Resolution to download album covers at",
)
@click.option(
    "-cd",
    "--album-cover-dir",
    "album_cover_dir",
    type=click.Path(),
    default="albums",
    show_default=True,
    help="Location to save cached album covers",
)
@click.option(
    "-fc",
    "--feature-cache",
    "feature_cache",
    type=click.File(),
    default=None,
    help="Use cached features from the given file",
)
@click.option(
    "--save-feature-cache",
    "save_feature_cache",
    is_flag=True,
    default=False,
    help="Cache image features to .features_cache",
)
def cli(ctx, **_kwargs):
    """Configurable Python album art collage generator for Spotify, featuring album discovery and
    color clustering."""
    Config.init(ctx)
    sp = get_sp()
    albums = Config.get("source").albums(sp)

    if Config.get("save_albums_cache"):
        with open(".albums_cache", "w", encoding="utf-8") as of:
            json.dump(albums, of)

    if Config.get("save_albums"):
        with open("albums.txt", "w", encoding="utf-8") as of:
            of.writelines([a["uri"] + "\n" for a in albums])

    album_cover_dir = Path(Config.get("album_cover_dir"))
    album_cover_dir.mkdir(exist_ok=True)
    album_cover_paths = []
    for i, album in enumerate(albums):
        cover_path = album_cover_dir / Path(f"{album['id']}.jpg")
        album_cover_paths.append(cover_path)
        print(f"Saving cover {i+1}/{len(albums)}", end="\r")
        if not cover_path.exists():
            download_cover(album, cover_path)
    print()

    features_json = {}
    if Config.get("feature_cache"):
        print("Using cached features")
        features_json = json.load(Config.get("feature_cache"))
    else:
        for i, a in enumerate(album_cover_paths):
            print(f"Getting features for art {i+1}/{len(album_cover_paths)}", end="\r")
            features_json[str(a)] = collage.get_features(a)
        print()

    if Config.get("save_feature_cache"):
        with open(".features_cache", "w", encoding="utf-8") as of:
            json.dump(features_json, of)

    features_to_path = {tuple(features): image for image, features in features_json.items()}
    features = list(features_to_path.keys())

    clusters = collage.get_clusters(features, 3)
    collage.sort_features_by_distance(features, clusters[0])

    collage.row_collage(features, features_to_path)
