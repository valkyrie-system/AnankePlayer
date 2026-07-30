import requests
import time
from PyQt6.QtCore import QThread, pyqtSignal

class SoulSeekDownloadThread(QThread):
    """
    Searches slskd for a release and automatically queues the best match for download.
    Requires slskd to be running locally or accessible via network.
    """
    status_message = pyqtSignal(str)
    download_started = pyqtSignal(str, str)  # artist, release
    error = pyqtSignal(str)

    def __init__(self, artist: str, release: str, api_url: str = "http://localhost:5030", api_key: str = ""):
        super().__init__()
        self.artist = artist
        self.release = release
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def run(self):
        query = f'{self.artist} "{self.release}" flac'
        self.status_message.emit(f"🦑 Searching Soulseek for: {query}")

        headers = {"X-API-Key": self.api_key} if self.api_key else {}

        try:
            # 1. Initiate Search
            resp = requests.post(f"{self.api_url}/api/v0/searches",
                                 json={"query": query}, headers=headers, timeout=10)
            resp.raise_for_status()
            search_id = resp.json().get("id")

            if not search_id:
                self.error.emit("slskd did not return a search ID.")
                return

            # 2. Poll for results (wait up to 15 seconds)
            best_match = None
            for _ in range(15):
                time.sleep(1)
                r = requests.get(f"{self.api_url}/api/v0/searches/{search_id}", headers=headers, timeout=10)
                r.raise_for_status()
                data = r.json()

                # Find a directory matching the release name with FLACs and seeders
                for file in data.get("response", {}).get("files", []):
                    if file.get("filename", "").endswith(".flac") and file.get("uploadSpeed", 0) > 0:
                        best_match = file
                        break

                if best_match:
                    break

            if not best_match:
                self.status_message.emit("No suitable FLAC matches found on Soulseek.")
                return

            # 3. Queue Download
            self.status_message.emit(f"Found match! Queuing download from {best_match.get('username')}...")
            dl_resp = requests.post(f"{self.api_url}/api/v0/transfers/downloads/queue",
                                    json={
                                        "username": best_match.get("username"),
                                        "files": [best_match.get("filename")]
                                    }, headers=headers, timeout=10)
            dl_resp.raise_for_status()

            self.download_started.emit(self.artist, self.release)
            self.status_message.emit(f"Download queued in slskd. It will appear in your Watch Folder soon!")

        except requests.exceptions.ConnectionError:
            self.error.emit("Could not connect to slskd. Is it running?")
        except Exception as e:
            self.error.emit(f"Soulseek error: {str(e)}")
