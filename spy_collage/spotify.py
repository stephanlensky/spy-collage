import configparser
from os import environ

import dateparser
import spotify_uri
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

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


def get_sp(credentials_path="spotify_credentials.ini") -> Spotify:
    client_id, client_secret = __read_credentials(credentials_path)
    environ["SPOTIPY_CLIENT_ID"] = client_id
    environ["SPOTIPY_CLIENT_SECRET"] = client_secret
    spotify = Spotify(client_credentials_manager=SpotifyClientCredentials())
    return spotify


def __is_duplicate_track(t1: dict, t2: dict) -> bool:
    matching_name = t1["name"] == t2["name"]
    matching_artists = len(t1["artists"]) == len(t2["artists"])
    for a1, a2 in zip(t1["artists"], t2["artists"]):
        if a1["uri"] != a2["uri"]:
            matching_artists = False
    matching_duration = abs(t1["duration_ms"] - t2["duration_ms"]) < 2000

    return matching_name and matching_artists and matching_duration


def discover_album(sp: Spotify, track: dict) -> tuple[dict, bool]:
    """
    If the supplied track URI is a single release, attempts to locate a full album release that
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

        if album["uri"] in __discovery_cache:
            album_tracks = __discovery_cache[album["uri"]]
        else:
            album_tracks = __collect_all_items(sp, sp.album_tracks(album["uri"]))
            __discovery_cache[album["uri"]] = album_tracks

        for album_track in album_tracks:
            if __is_duplicate_track(track, album_track):
                return album, True

    return track["album"], False


def collect_albums(sp: Spotify, uris: list[str], discovery_enabled: bool = True) -> list[dict]:
    albums = []
    for uri in uris:
        parsed = spotify_uri.parse(uri)
        tracks = []
        if parsed.type == "album":
            albums.append(sp.album(uri))
        elif parsed.type == "playlist":
            print(f"Collecting items from playlist {uri}...")
            playlist_tracks = __collect_all_items(sp, sp.playlist(uri)["tracks"])
            for t in playlist_tracks:
                tracks.append(t["track"])
        elif parsed.type == "track":
            tracks.append(sp.track(uri))

        for i, t in enumerate(tracks):
            print(f"Processing track {i+1}/{len(tracks)}")
            if discovery_enabled:
                album, _ = discover_album(sp, t)
            else:
                album = t["album"]
            albums.append(album)

    return albums
