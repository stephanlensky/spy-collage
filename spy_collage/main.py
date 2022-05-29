import json
from pathlib import Path
from typing import List

import typer

from spy_collage import collage
from spy_collage.cli import format_error, format_info
from spy_collage.cli.params import AlbumSource, AlbumSourceParam, CollageSize, CollageSizeParam
from spy_collage.cli.typer_patches import patch_typer_support_custom_types, register_type
from spy_collage.models import AlbumCoverResolution
from spy_collage.presets import load_preset
from spy_collage.spotify import collect_albums, download_cover

ALBUM_DOWNLOAD_PATH = Path("albums")
FEATURES_CACHE_PATH = Path(".features_cache")


patch_typer_support_custom_types()
register_type(AlbumSource, lambda v: AlbumSourceParam().convert(v))
register_type(CollageSize, lambda v: CollageSizeParam().convert(v))
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
    dimensions: CollageSize = typer.Option(
        ..., "--dimensions", "-d", help="Dimensions of the generated collage, specified as nxm"
    ),
    preset: str = typer.Option(
        ...,
        "--preset",
        "-p",
        help=(
            "Color arrangement preset to use for generating the collage. Available presets are"
            " defined in presets.ini."
        ),
    ),
    discover: bool = typer.Option(
        False, help="Enable/disable automatic album discovery for singles"
    ),
    market: str = typer.Option(
        "US", help="When discovering albums, only consider those available in this market"
    ),
    dedupe: bool = typer.Option(
        False,
        help="Experimental: When fetching album art, skip albums whose art is identical to an already-fetched album",
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

    if len(albums) < dimensions.width * dimensions.height:
        typer.echo(
            format_error(
                f"product of width and height dimensions ({dimensions.width} x"
                f" {dimensions.height} = {dimensions.width * dimensions.height}) must be less than or equal to"
                f" the number of albums provided ({len(albums)})"
            )
        )
        raise typer.Abort()
    if len(albums) > dimensions.width * dimensions.height:
        typer.echo(
            format_info(
                f"more albums were provided ({len(albums)}) than spaces in collage"
                f" ({dimensions.width} x {dimensions.height} ="
                f" {dimensions.width * dimensions.height}). Will use the"
                f" {dimensions.width * dimensions.height} albums that best match the requested"
                " colors."
            )
        )

    key_objects = load_preset(preset, dimensions.width, dimensions.height)

    if save_albums:
        with open("albums.txt", "w", encoding="utf-8") as of:
            of.writelines([a["uri"] + "\n" for a in albums])

    ALBUM_DOWNLOAD_PATH.mkdir(exist_ok=True)
    album_cover_paths = []
    for i, album in enumerate(albums):
        cover_path = ALBUM_DOWNLOAD_PATH / Path(f"{album['id']}_{album_cover_resolution.value}.jpg")
        album_cover_paths.append(cover_path)
        print(f"Saving cover {i+1}/{len(albums)}", end="\r")
        if not cover_path.exists():
            download_cover(album, cover_path, album_cover_resolution)
    print()

    features: List[collage.ImageFeatures] = []

    # this feature does not work properly right now with changing sources across multiple runs
    # disable for now
    if False:  # pylint: disable=using-constant-test
        # if FEATURES_CACHE_PATH.exists():
        print("Using cached features")
        features_json = json.load(FEATURES_CACHE_PATH.open(encoding="utf-8"))
        for f in features_json:
            features.append(collage.ImageFeatures.from_dict(f))
    else:
        for i, a in enumerate(album_cover_paths):
            print(f"Getting features for art {i+1}/{len(album_cover_paths)}", end="\r")
            new_feature = collage.get_features(a)

            # could save minimal runtime by keeping a set of phashes rather than pairwise comparisons,
            # but many remix albums are simple art recolors that might get missed by the luminance-based
            # phash algorithm, so we still need to do pairwise color comparisons.
            if dedupe:
                present = False
                for feature in features:
                    if new_feature.is_likely_duplicate(feature):
                        present = True
                        break
                if not present:
                    features.append(new_feature)
            else:
                features.append(new_feature)
        print()
        if dedupe:
            print(f"Found {len(features)} unique album covers", end="\n")
            if len(features) < dimensions.width * dimensions.height:
                typer.echo(
                    format_error(
                        f"product of width and height dimensions ({dimensions.width} x"
                        f" {dimensions.height} = {dimensions.width * dimensions.height}) must be less than or equal to"
                        f" the number of unique album covers({len(features)})"
                    )
                )

    # with open(".features_cache", "w", encoding="utf-8") as of:
    #     json.dump([f.to_dict() for f in features], of)

    collage.lap_collage(features, (dimensions.width, dimensions.height), key_objects)
