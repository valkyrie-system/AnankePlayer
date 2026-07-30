import requests
from datetime import datetime, timezone

class ListenBrainzSubmitter:
    def __init__(self, ds):
        self.ds = ds

    def submit_listen(self, artist: str, track: str, album: str):
        token = self.ds.settings.get("listenbrainz_token", "").strip()
        if not token:
            return False

        payload = {
            "listen_type": "single",
            "payload": [
                {
                    "listened_at": int(datetime.now(timezone.utc).timestamp()),
                    "track_metadata": {
                        "artist_name": artist,
                        "track_name": track,
                        "release_name": album,
                        "additional_info": {
                            "submission_client": "MusicWatcher",
                            "submission_client_version": "5.1"
                        }
                    }
                }
            ]
        }

        try:
            r = requests.post("https://api.listenbrainz.org/1/submit-listens",
                              json=payload,
                              headers={"Authorization": f"Token {token}"},
                              timeout=10)
            return r.status_code == 200
        except Exception:
            return False
