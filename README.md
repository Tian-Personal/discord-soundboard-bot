# discord-soundboard-bot

A Discord bot that plays YouTube audio in a voice channel. Search for a song by
name, paste a link, or save sounds under a short name to reuse later. Anything
requested while a track is playing gets queued rather than rejected.

## Requirements

- Python 3.8+
- [ffmpeg](https://ffmpeg.org/download.html) on your `PATH` (or set `FFMPEG_PATH`)
- A Discord bot application with the **Message Content Intent** enabled

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate        # on Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Copy the example config and fill in your bot token:

```bash
cp .env.example .env
```

Get the token from the [Discord Developer Portal](https://discord.com/developers/applications)
under **Bot -> Reset Token**, and enable **Message Content Intent** on the same
page. Without that intent the bot connects but never sees your commands.

Invite the bot to your server via **OAuth2 -> URL Generator** with the `bot`
scope and the **Connect** and **Speak** permissions.

Then run it:

```bash
python main.py
```

## Commands

| Command | Description |
| --- | --- |
| `!play <search words>` | Search YouTube and play the top result |
| `!play <youtube url>` | Play a link directly |
| `!play <name>` | Play a previously saved sound |
| `!save <name> <url or search>` | Download a sound and keep it under that name |
| `!queue` | Show what is waiting to play |
| `!pause` / `!resume` | Pause and unpause the current track |
| `!skip` | Skip to the next thing in the queue |
| `!stop` | Clear the queue and disconnect |

The bot joins whichever voice channel the caller is currently in, plays through
the queue, and leaves once the queue is empty. A saved sound whose name matches
your input takes priority over searching for it.

## Configuration

All configuration lives in `.env` — see `.env.example`.

| Variable | Required | Description |
| --- | --- | --- |
| `TOKEN` | yes | Discord bot token |
| `ANNOUNCE_GUILD` | no | Server name to post the command list in on startup |
| `ANNOUNCE_CHANNEL` | no | Channel name to post that list in |
| `FFMPEG_PATH` | no | Full path to `ffmpeg.exe`, if it is not on your `PATH` |
| `COMMAND_PREFIX` | no | Command prefix, defaults to `!` |
| `SOUNDS_FOLDER` | no | Where saved sounds live, defaults to `saved-sounds` |

Leave `ANNOUNCE_GUILD` or `ANNOUNCE_CHANNEL` blank to skip the startup message.
Both are matched by name, case-insensitively.

## Notes

Downloads go through [yt-dlp](https://github.com/yt-dlp/yt-dlp), which replaced
`pytube` after it stopped working against YouTube. Tracks played from a URL or a
search are downloaded to a temporary file and deleted after playing; only
`!save` keeps anything on disk.
