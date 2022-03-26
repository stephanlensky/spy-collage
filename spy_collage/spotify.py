import asyncio
import configparser
from os import environ
from pathlib import Path
from typing import Optional

import dateparser
import requests
import spotify
import spotify_uri
import typer
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

from spy_collage.async_utils import run_until_complete_with_progress
from spy_collage.cli import format_error
from spy_collage.models import AlbumCoverResolution


def __read_credentials(credentials_path):
    config = configparser.ConfigParser()
    config.read(credentials_path)
    try:
        return config["spotify"]["client_id"], config["spotify"]["client_secret"]
    except KeyError:
        typer.echo(format_error("Missing Spotify credentials in spotify_credentials.ini"))
        raise typer.Exit()


def __collect_all_items(sp, results) -> list[dict]:
    items = results["items"]
    while results["next"]:
        results = sp.next(results)
        items.extend(results["items"])
    return items


__sp: Optional[Spotify] = None


def get_client(credentials_path="spotify_credentials.ini") -> spotify.Client:
    client_id, client_secret = __read_credentials(credentials_path)
    return spotify.Client(client_id, client_secret)


def close_client(client: spotify.Client):
    async def do_close():
        await client.close()

    asyncio.run(do_close())


def get_spotify(credentials_path="spotify_credentials.ini") -> Spotify:
    global __sp  # pylint: disable=global-statement
    if __sp is not None:
        return __sp
    client_id, client_secret = __read_credentials(credentials_path)
    environ["SPOTIPY_CLIENT_ID"] = client_id
    environ["SPOTIPY_CLIENT_SECRET"] = client_secret
    s = Spotify(client_credentials_manager=SpotifyClientCredentials(), requests_timeout=15)
    __sp = s
    return s


def __is_duplicate_track(t1: dict, t2: dict) -> bool:
    matching_name = t1["name"] == t2["name"]
    matching_artists = len(t1["artists"]) == len(t2["artists"])
    for a1, a2 in zip(t1["artists"], t2["artists"]):
        if a1["uri"] != a2["uri"]:
            matching_artists = False
    matching_duration = abs(t1["duration_ms"] - t2["duration_ms"]) < 2000

    return matching_name and matching_artists and matching_duration


def discover_album(
    track: dict, user_market: str, cache: Optional[dict[str, list[dict]]] = None
) -> tuple[dict, bool]:
    """
    If the supplied track is a single release, attempts to locate a full album release that
    contains the track.

    If one cannot be found, returns the album of the given track as-is.
    """
    sp = get_spotify()
    if cache is None:
        cache = {}
    if track["album"]["album_type"] == "album" and (
        "album_group" not in track["album"] or track["album"]["album_group"] == "album"
    ):
        return track["album"], False

    track_album_release_date = dateparser.parse(track["album"]["release_date"])
    assert track_album_release_date is not None

    album_artist_uri = track["album"]["artists"][0]["uri"]
    if album_artist_uri in cache:
        albums = cache[album_artist_uri]
    else:
        albums = __collect_all_items(sp, sp.artist_albums(album_artist_uri, album_type="album"))
        cache[album_artist_uri] = albums

    for album in albums:
        album_release_date = dateparser.parse(album["release_date"])
        assert album_release_date is not None
        if album_release_date < track_album_release_date:
            continue
        if user_market and user_market not in album["available_markets"]:
            continue
        if len(album["artists"]) > 1:
            continue  # this is likely a compilation album (e.g. Ophelia Vol 2 by Seven Lions)

        if album["uri"] in cache:
            album_tracks = cache[album["uri"]]
        else:
            album_tracks = __collect_all_items(sp, sp.album_tracks(album["uri"]))
            cache[album["uri"]] = album_tracks

        for album_track in album_tracks:
            if __is_duplicate_track(track, album_track):
                return album, True

    return track["album"], False


def collect_albums(uris: list[str], discovery_enabled: bool, user_market: str) -> list[dict]:
    PROGRESS_LABEL_LJUST = 20

    client = get_client()
    tracks: list = []
    albums: list = []

    parsed_uris = map(spotify_uri.parse, uris)
    playlist_ids = []
    album_ids = []
    track_ids = []
    for parsed_uri in parsed_uris:
        resource_id = parsed_uri.id
        if parsed_uri.type == "playlist":
            playlist_ids.append(resource_id)
        elif parsed_uri.type == "album":
            album_ids.append(resource_id)
        elif parsed_uri.type == "track":
            track_ids.append(resource_id)

    try:
        if playlist_ids:
            playlist_tasks = [
                client.http.get_playlist(id, fields="id,tracks(total,limit),href")
                for id in playlist_ids
            ]
            playlists = run_until_complete_with_progress(
                playlist_tasks, "Collecting playlists".ljust(PROGRESS_LABEL_LJUST)
            )
            total_tracks = sum((p["tracks"]["total"] for p in playlists))

            tracks_tasks = [
                client.http.get_playlist_tracks(
                    p["id"],
                    offset=i,
                    limit=p["tracks"]["limit"],
                )
                for p in playlists
                for i in range(0, p["tracks"]["total"], p["tracks"]["limit"])
            ]
            tracks.extend(
                run_until_complete_with_progress(
                    tracks_tasks,
                    "Collecting tracks".ljust(PROGRESS_LABEL_LJUST),
                    length=total_tracks,
                    transform_result=lambda r: r["items"],
                    unpack_result=True,
                )
            )

        discovery_cache: dict[str, list[dict]] = {}
        for i, t in enumerate(tracks):
            print(f"Processing track {i+1}/{len(tracks)}", end="\r")
            if discovery_enabled:
                album, discovered = discover_album(t, user_market, cache=discovery_cache)
                if discovered:
                    print(
                        f"    * Discovered album {album['name']} for {t['artists'][0]['name']} -"
                        f" {t['album']['name']}"
                    )
            else:
                album = t["album"]
            albums.append(album)
        if tracks:
            print()
    finally:
        close_client(client)

    return album_ids


def download_cover(album: dict, size: AlbumCoverResolution, path: Path):
    images = album["images"]
    images.sort(key=lambda i: i["width"])
    if size == AlbumCoverResolution.small:
        url = images[0]["url"]
    elif size == AlbumCoverResolution.medium:
        url = images[int(len(images) / 2)]["url"]
    else:
        url = images[-1]["url"]

    r = requests.get(url)
    with open(path, "wb") as of:
        of.write(r.content)
