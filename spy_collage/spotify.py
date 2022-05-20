import configparser
from functools import cache
from os import environ
from pathlib import Path

import dateparser
import requests
import spotify_uri
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

from spy_collage.models import AlbumCoverResolution

__discovery_cache: dict[str, list[dict]] = {}


def __read_credentials(credentials_path):
    config = configparser.ConfigParser()
    config.read(credentials_path)
    return config["spotify"]["client_id"], config["spotify"]["client_secret"]


def __collect_all_items(sp: Spotify, results) -> list[dict]:
    items = results["items"]
    while results["next"]:
        results = sp.next(results)
        items.extend(results["items"])
    return items


@cache
def get_sp(credentials_path="spotify_credentials.ini") -> Spotify:
    if "SPOTIPY_CLIENT_ID" not in environ or "SPOTIPY_CLIENT_SECRET" not in environ:
        print("Reading Spotify credentials from spotify_credentials.ini...")
        client_id, client_secret = __read_credentials(credentials_path)
        environ["SPOTIPY_CLIENT_ID"] = client_id
        environ["SPOTIPY_CLIENT_SECRET"] = client_secret
    spotify = Spotify(client_credentials_manager=SpotifyClientCredentials(), requests_timeout=15)
    return spotify


def __is_duplicate_track(t1: dict, t2: dict) -> bool:
    matching_name = t1["name"] == t2["name"]
    matching_artists = len(t1["artists"]) == len(t2["artists"])
    for a1, a2 in zip(t1["artists"], t2["artists"]):
        if a1["uri"] != a2["uri"]:
            matching_artists = False
    matching_duration = abs(t1["duration_ms"] - t2["duration_ms"]) < 2000

    return matching_name and matching_artists and matching_duration


def discover_album(sp: Spotify, track: dict, user_market: str) -> tuple[dict, bool]:
    """
    If the supplied track is a single release, attempts to locate a full album release that
    contains the track.

    If one cannot be found, returns the album of the given track as-is.
    """
    if track["album"]["album_type"] == "album" and (
        "album_group" not in track["album"] or track["album"]["album_group"] == "album"
    ):
        return track["album"], False
    track_album_release_date = dateparser.parse(track["album"]["release_date"])
    assert track_album_release_date is not None

    album_artist_uri = track["album"]["artists"][0]["uri"]
    if album_artist_uri in __discovery_cache:
        albums = __discovery_cache[album_artist_uri]
    else:
        albums = __collect_all_items(sp, sp.artist_albums(album_artist_uri, album_type="album"))
        __discovery_cache[album_artist_uri] = albums

    for album in albums:
        album_release_date = dateparser.parse(album["release_date"])
        assert album_release_date is not None
        if album_release_date < track_album_release_date:
            continue
        if user_market and user_market not in album["available_markets"]:
            continue
        if len(album["artists"]) > 1:
            continue  # this is likely a compilation album (e.g. Ophelia Vol 2 by Seven Lions)

        if album["uri"] in __discovery_cache:
            album_tracks = __discovery_cache[album["uri"]]
        else:
            album_tracks = __collect_all_items(sp, sp.album_tracks(album["uri"]))
            __discovery_cache[album["uri"]] = album_tracks

        for album_track in album_tracks:
            if __is_duplicate_track(track, album_track):
                return album, True

    return track["album"], False


def collect_albums(
    uris: list[str], discovery_enabled: bool = True, user_market: str = "US"
) -> list[dict]:
    sp = get_sp()

    albums = []
    tracks = []
    for i, uri in enumerate(uris):
        print(f"Processing input {i+1}/{len(uris)}", end="\r")
        parsed = spotify_uri.parse(uri)
        if parsed.type == "album":
            albums.append(sp.album(uri))
        elif parsed.type == "playlist":
            print(f"Collecting items from playlist {uri}...")
            playlist_tracks = __collect_all_items(sp, sp.playlist(uri)["tracks"])
            for t in playlist_tracks:
                tracks.append(t["track"])
        elif parsed.type == "track":
            tracks.append(sp.track(uri))
    print()

    for i, t in enumerate(tracks):
        print(f"Processing track {i+1}/{len(tracks)}", end="\r")
        if discovery_enabled:
            album, discovered = discover_album(sp, t, user_market=user_market)
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

    return albums


def download_cover(album: dict, path: Path, size: AlbumCoverResolution):
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
