#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import typing
from io import BytesIO
from pathlib import Path

import requests
from tidal_api import tidalapi
from mutagen import id3
from mutagen.flac import Picture, FLAC, FLACNoHeaderError


def download_flac(track: tidalapi.models.Track, file_path, album=None):
    if album is None:
        album = track.album
    url = session.get_media_url(track_id=track.id)

    r = requests.get(url, stream=True)
    r.raw.decode_content = True
    data = BytesIO()
    shutil.copyfileobj(r.raw, data)
    data.seek(0)
    audio = FLAC(data)

    # general metatags
    audio['artist'] = [x.name for x in track.artists]
    audio['title'] = f'{track.name}{f" ({track.version})" if track.version else ""}'
    audio['albumartist'] = album.artist.name
    audio['album'] = album.name
    audio['date'] = str(album.year)

    # album related metatags
    audio['discnumber'] = str(track.volumeNumber)
    audio['disctotal'] = str(album.numberOfVolumes)
    audio['tracknumber'] = str(track.trackNumber)
    audio['tracktotal'] = str(album.numberOfTracks)

    # Tidal sometimes returns null for track copyright
    if track.copyright:
        audio['copyright'] = track.copyright
    elif album.copyright:
        audio['copyright'] = album.copyright

    # identifiers for later use in own music libraries
    if track.isrc:
        audio['isrc'] = track.isrc
    if album.upc:
        audio['upc'] = album.upc

    pic = Picture()
    pic.type = id3.PictureType.COVER_FRONT
    pic.width = 640
    pic.height = 640
    pic.mime = 'image/jpeg'
    r = requests.get(track.album.image, stream=True)
    r.raw.decode_content = True
    pic.data = r.raw.read()

    audio.add_picture(pic)

    data.seek(0)
    audio.save(data)
    with open(file_path, "wb") as f:
        data.seek(0)
        shutil.copyfileobj(data, f)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument('login', help="TIDAL login/email")
    p.add_argument('password', help="TIDAL password")
    p.add_argument('output_dir', help="output directory (download target)")
    p.add_argument('--api_token', help="TIDAL API token", default='BI218mwp9ERZ3PFI')
    args = p.parse_args()

    config = tidalapi.Config(tidalapi.Quality.lossless)
    config.api_token = args.api_token
    session = tidalapi.Session(config)
    session.login(args.login, args.password)

    print("Tidal FLAC ripper")
    while True:
        folder = Path(args.output_dir)
        folder.mkdir(parents=True, exist_ok=True)

        print("0) Search for track")
        print("1) Download track")
        print("2) Download album")
        print("3) Download playlist")
        mode = input("Select mode: ")

        # TODO: download queue
        # TODO: search for album
        # TODO: search for artist
        # TODO: search for playlist
        try:
            if mode == "0":
                search_query = input("Enter search query: ")
                search = session.search(field='track', value=search_query)
                for track in search.tracks:
                    # TODO: selector to download
                    print(f"{track.id}: {track.artist.name} - {track.name}")

            elif mode == "1":
                track_id = input("Enter track id: ")
                track = session.get_track(track_id, withAlbum=True)
                track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                print(f'Downloading track: {track.artist.name} - {track_name}')
                download_flac(track, folder / f'{track.artist.name} - {track_name}.flac'.replace("/", "_"))
                print("Track downloaded!")

            elif mode == "2":
                album_id = input("Enter album id: ")
                album = session.get_album(album_id=album_id)                # type: tidalapi.models.Album
                print(f'Downloading album: {album.artist.name} - {album.name}')
                tracks = session.get_album_tracks(album_id=album_id)        # type: typing.Iterable[tidalapi.models.Track]
                num = 0
                # TODO: handle multicd albums better (separate dirs and playlists?)
                discs = max(map(lambda x: x.disc_num, tracks))
                folder = folder / album.artist.name.replace("/", "_") / f'{f"({album.release_date.year}) " if album.release_date is not None else ""}{album.name}'.replace("/", "_")
                folder.mkdir(parents=True, exist_ok=True)
                with open(folder / f'00. {album.name.replace("/", "_")}.m3u', 'w') as playlist_file:
                    for track in tracks:
                        num += 1
                        track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                        print(f'Downloading ({num}/{album.num_tracks}): {track_name}')
                        fname = f'{str(track.track_num).zfill(2)}. {track_name.replace("/", "_")}.flac'
                        download_flac(track, folder / fname, album=album)
                        playlist_file.write(fname)
                        playlist_file.write("\n")
                print("Album downloaded!")

            elif mode == "3":
                playlist_id = input("Enter playlist id: ")
                playlist = session.get_playlist(playlist_id=playlist_id)
                tracks = session.get_playlist_tracks(playlist_id=playlist_id)
                print(f'Downloading playlist: {playlist.name}')
                num = 0
                folder = folder / playlist.name.replace("/", "_")
                folder.mkdir(parents=True, exist_ok=True)
                with open(folder / f'{playlist.name.replace("/", "_")}.m3u', "w") as playlist_file:
                    for track in tracks:
                        num += 1
                        track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                        print(f'Downloading ({num}/{playlist.num_tracks}): {track_name}')
                        fname = f'{track.artist.name} - {track_name}.flac'.replace("/", "_")
                        download_flac(track, folder / fname)
                        playlist_file.write(fname)
                        playlist_file.write("\n")
                print("Playlist downloaded!")

            else:
                print("Incorrect mode!")

        except FLACNoHeaderError:
            print("This track is not available in lossless quality, abandoning")
        except Exception as e:
            print(f"Error occured: {e}")

        if input("Do you want to continue? [y/n] ") != "y":
            break
