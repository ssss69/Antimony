import os
import time

from antimony_core import AssistantAPI, AnimeAssistant


def main():
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8765"))
    assistant = AnimeAssistant("soren")
    api = AssistantAPI(assistant, serve_frontend=True)
    url = api.start(host=host, port=port)
    print(f"Antimony public server: {url}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        api.stop()


if __name__ == "__main__":
    main()
