import os
import re
import shutil
import asyncio
import discord
import yt_dlp
from collections import deque
from dotenv import load_dotenv
from discord import FFmpegPCMAudio
from discord.ext import commands

load_dotenv()

TOKEN = os.getenv("TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
SOUNDS_FOLDER = os.getenv("SOUNDS_FOLDER", "saved-sounds")
FFMPEG = os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg")

# Where to post the command list on startup. Blank disables the announcement.
ANNOUNCE_GUILD = os.getenv("ANNOUNCE_GUILD", "").lower()
ANNOUNCE_CHANNEL = os.getenv("ANNOUNCE_CHANNEL", "").lower()

INSTRUCTIONS = f"""**Soundboard bot is up.** Join a voice channel, then:
`{COMMAND_PREFIX}play <search words>` - search youtube and play the top hit
`{COMMAND_PREFIX}play <youtube url>` - play a link directly
`{COMMAND_PREFIX}play <name>` - play a saved sound
`{COMMAND_PREFIX}save <name> <url or search>` - save a sound to reuse later
`{COMMAND_PREFIX}queue` - see what is up next
`{COMMAND_PREFIX}pause` / `{COMMAND_PREFIX}resume` - pause and unpause
`{COMMAND_PREFIX}skip` - jump to the next thing in the queue
`{COMMAND_PREFIX}stop` - clear the queue and disconnect
Anything already playing gets queued instead of interrupted."""

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# One queue and one player task per server, so servers do not stomp each other
queues = {}
players = {}
temp_count = 0
instructions_posted = False

# Matches a YouTube link; anything else is treated as a name or a search
YOUTUBE_PATTERN = re.compile(
    r'(https?://)?(www\.)?'
    r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
    r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')


def is_youtube_url(url):
    return YOUTUBE_PATTERN.match(url) is not None


def download_audio(name, target):
    """Download audio to SOUNDS_FOLDER/<name>.mp3.

    target is a URL, or "ytsearch1:<query>" to take the top search hit.
    Returns the track title, or None if the download failed.
    """
    os.makedirs(SOUNDS_FOLDER, exist_ok=True)

    opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{SOUNDS_FOLDER}/{name}.%(ext)s",
        "final_ext": "mp3",
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3"}],
        "ffmpeg_location": FFMPEG,
        "noplaylist": True,
        "quiet": True,
        "noprogress": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=True)

        # A search comes back as a playlist of results, so take the first
        if "entries" in info:
            info = info["entries"][0]

        title = info.get("title", name)
        print(f"Downloaded '{title}' as {name}.mp3")
        return title
    except Exception as error:
        print(f"Download failed for {target}: {error}")
        return None


async def player_loop(ctx, vc):
    """Drain this server's queue one sound at a time, then leave."""
    guild_id = ctx.guild.id
    queue = queues[guild_id]
    loop = asyncio.get_running_loop()

    while queue:
        label, file_path, is_temp = queue.popleft()
        finished = asyncio.Event()

        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            loop.call_soon_threadsafe(finished.set)

        try:
            audio_source = FFmpegPCMAudio(file_path, executable=FFMPEG)
            await ctx.send(f"Playing {label}.")
            vc.play(audio_source, after=after_playing)

            # Wait for the track to end, or for skip/stop to cut it short
            await finished.wait()
            print(f"Done playing {label}.")
        except Exception as error:
            print(f"Could not play {label}: {error}")
            await ctx.send("Something went wrong oopsie daisy.")

        if is_temp and os.path.exists(file_path):
            os.remove(file_path)

    players.pop(guild_id, None)
    if vc.is_connected():
        await vc.disconnect()


async def post_instructions():
    """Announce the controls in the configured channel, once per startup."""
    global instructions_posted

    if instructions_posted or not ANNOUNCE_GUILD or not ANNOUNCE_CHANNEL:
        return

    guild = discord.utils.find(
        lambda g: g.name.lower() == ANNOUNCE_GUILD, bot.guilds)
    if guild is None:
        print(f"No server called '{ANNOUNCE_GUILD}'. "
              f"I am in: {[g.name for g in bot.guilds]}")
        return

    channel = discord.utils.find(
        lambda c: c.name.lower() == ANNOUNCE_CHANNEL, guild.text_channels)
    if channel is None:
        print(f"No #{ANNOUNCE_CHANNEL} channel in '{guild.name}'. "
              f"Channels: {[c.name for c in guild.text_channels]}")
        return

    try:
        await channel.send(INSTRUCTIONS)
        instructions_posted = True
        print(f"Posted instructions to #{channel.name} in '{guild.name}'.")
    except discord.Forbidden:
        print(f"Not allowed to post in #{channel.name}.")


def get_voice_client(ctx):
    return discord.utils.get(bot.voice_clients, guild=ctx.guild)


@bot.event
async def on_ready():
    # on_ready fires again on reconnects, so post_instructions guards itself
    print(f"We have logged in as {bot.user}")
    await post_instructions()


@bot.command(name="save")
async def save_sound(ctx, name, *, url):
    """Download a sound and keep it under the given name."""
    target = url if is_youtube_url(url) else f"ytsearch1:{url}"

    if download_audio(name, target):
        await ctx.send(f"Saved audio as {name}.")
    else:
        await ctx.send(f"Couldn't download {name}.")


@bot.command(name="play")
async def play_sound(ctx, *, name_or_url):
    """Play a saved sound, a YouTube link, or the top hit for a search."""
    global temp_count

    if not ctx.author.voice:
        await ctx.send("You're not in a voice channel.")
        return

    saved_path = f"{SOUNDS_FOLDER}/{name_or_url}.mp3"
    is_temp = False

    if os.path.exists(saved_path):
        # A sound saved under this name beats searching for it
        label = name_or_url
        file_path = saved_path
    else:
        is_temp = True
        temp_count += 1
        temp_name = f"temp-{ctx.guild.id}-{temp_count}"
        file_path = f"{SOUNDS_FOLDER}/{temp_name}.mp3"

        if is_youtube_url(name_or_url):
            target = name_or_url
            await ctx.send("Downloading...")
        else:
            target = f"ytsearch1:{name_or_url}"
            await ctx.send(f"Searching for *{name_or_url}*...")

        label = download_audio(temp_name, target)
        if label is None:
            await ctx.send("Couldn't find that one.")
            return

    if not os.path.exists(file_path):
        await ctx.send("Something went wrong grabbing that.")
        return

    # Join the voice channel of whoever called the command
    channel = ctx.author.voice.channel
    vc = get_voice_client(ctx)
    if vc and vc.is_connected():
        await vc.move_to(channel)
    else:
        vc = await channel.connect()

    queue = queues.setdefault(ctx.guild.id, deque())
    queue.append((label, file_path, is_temp))

    player = players.get(ctx.guild.id)
    if player and not player.done():
        await ctx.send(f"Queued {label} at position {len(queue)}.")
    else:
        players[ctx.guild.id] = asyncio.create_task(player_loop(ctx, vc))


@bot.command(name="queue")
async def show_queue(ctx):
    """List what is waiting to play."""
    queue = queues.get(ctx.guild.id)
    if not queue:
        await ctx.send("Nothing queued up.")
        return

    lines = [f"{i}. {label}" for i, (label, _, _) in enumerate(queue, start=1)]
    await ctx.send("Up next:\n" + "\n".join(lines))


@bot.command(name="pause")
async def pause_sound(ctx):
    """Pause the current track."""
    vc = get_voice_client(ctx)

    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("Paused.")
    else:
        await ctx.send("Nothing is playing.")


@bot.command(name="resume")
async def resume_sound(ctx):
    """Resume a paused track."""
    vc = get_voice_client(ctx)

    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("Resumed.")
    else:
        await ctx.send("Nothing is paused.")


@bot.command(name="skip")
async def skip_sound(ctx):
    """Stop the current track so the player moves to the next one."""
    vc = get_voice_client(ctx)

    # stop() fires the after callback, which lets player_loop continue
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await ctx.send("Skipped.")
    else:
        await ctx.send("Nothing is playing.")


@bot.command(name="stop")
async def disconnect(ctx):
    """Clear the queue and leave the voice channel."""
    vc = get_voice_client(ctx)

    if not (vc and vc.is_connected()):
        await ctx.send("I'm not connected to a voice channel.")
        return

    channel = vc.channel
    queue = queues.get(ctx.guild.id)
    if queue:
        queue.clear()

    vc.stop()
    await ctx.send(f"Disconnected from {channel}.")


def main():
    if not TOKEN:
        raise SystemExit(
            "No TOKEN found. Copy .env.example to .env and add your bot token.")
    if not FFMPEG:
        raise SystemExit(
            "ffmpeg not found. Install it, or set FFMPEG_PATH in .env.")

    bot.run(TOKEN)


if __name__ == "__main__":
    main()
