import json
from pathlib import Path

import typer

from spy_collage import collage
from spy_collage.cli.params import AlbumSource, AlbumSourceParam
from spy_collage.cli.typer_patches import patch_typer_support_custom_types, register_type
from spy_collage.models import AlbumCoverResolution
from spy_collage.spotify import collect_albums, download_cover

ALBUM_DOWNLOAD_PATH = Path("albums")
FEATURES_CACHE_PATH = Path(".features_cache")


patch_typer_support_custom_types()
register_type(AlbumSource, lambda v: AlbumSourceParam().convert(v))
app = typer.Typer()


@app.command()
def main(
    source: AlbumSource = typer.Argument(
        default=None,
        help=(
            "Albums to generate the collage with. Either a single Spotify playlist URI or a text"
            " file containing one of: a list of playlist URIs, a list of album URIs, or a JSON list"
            " of albums collected from the Spotify API."
        ),
    ),
    discover: bool = typer.Option(
        True, help="Enable/disable automatic album discovery for singles"
    ),
    market: str = typer.Option(
        "US", help="When discovering albums, only consider those available in this market"
    ),
    save_albums: bool = typer.Option(
        False, "--save-album-uris", help="Save processed album URIs to albums.txt"
    ),
    album_cover_resolution: AlbumCoverResolution = typer.Option(
        "medium", "--album-cover-resolution", "-r", help="Resolution to download album covers at"
    ),
):
    """A configurable album art collage generator for Spotify, featuring album discovery and
    color clustering."""
    albums = source.json_albums
    if not albums:
        albums = collect_albums(source.uris, discovery_enabled=discover, user_market=market)

    if save_albums:
        with open("albums.txt", "w", encoding="utf-8") as of:
            of.writelines([a["uri"] + "\n" for a in albums])

    ALBUM_DOWNLOAD_PATH.mkdir(exist_ok=True)
    album_cover_paths = []
    for i, album in enumerate(albums):
        cover_path = ALBUM_DOWNLOAD_PATH / Path(f"{album['id']}.jpg")
        album_cover_paths.append(cover_path)
        print(f"Saving cover {i+1}/{len(albums)}", end="\r")
        if not cover_path.exists():
            download_cover(album, cover_path, album_cover_resolution)
    print()

    features = []
    if FEATURES_CACHE_PATH.exists():
        print("Using cached features")
        features_json = json.load(FEATURES_CACHE_PATH.open(encoding="utf-8"))
        for f in features_json:
            features.append(collage.ImageFeatures.from_dict(f))
    else:
        for i, a in enumerate(album_cover_paths):
            print(f"Getting features for art {i+1}/{len(album_cover_paths)}", end="\r")
            features.append(collage.get_features(a))
        print()

    with open(".features_cache", "w", encoding="utf-8") as of:
        json.dump([f.to_dict() for f in features], of)

    collage.lap_collage(features, (12, 9))
