import os
import discord
import asyncio
import re
from dotenv import load_dotenv
from pytube import YouTube
from discord import FFmpegPCMAudio
from discord.ext import commands

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
output_folder = "saved-sounds"


def download_and_save_audio(filename, youtube_url):
    # Create the "saved-sounds" folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    try:
        # Download the YouTube video
        print("Downloading video...")
        yt = YouTube(youtube_url)
        video_stream = yt.streams.filter(only_audio=True).first()
        video_stream.download(filename=f"{output_folder}/{filename}.mp3")

        print(f"Audio saved successfully as {filename}.mp3 in the 'saved-sounds' folder.")
    except Exception as e:
        print(f"An error occurred: {e}")


def is_youtube_url(url):
    # Regular expression for matching YouTube video URLs
    youtube_pattern = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    match = re.match(youtube_pattern, url)
    return match is not None


def extract_youtube_video_id(url):
    # Regular expression for matching YouTube video URLs
    youtube_pattern = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    match = re.match(youtube_pattern, url)

    if match:
        return match.group(6)  # Extract the video ID from the match
    else:
        return None  # Return None if the URL doesn't match the pattern


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.command(name="print")
async def print_test(ctx, input):
    print(f"input: {input}")
    await ctx.send(f"you said {input}")


@bot.command(name="save")
async def save_sound(ctx, name, url):
    print("i've been called with {save}")

    download_and_save_audio(name, url)

    await ctx.send(f"Audio saved as {name}.")


@bot.command(name="play")
async def play_sound(ctx, name_or_url):
    print("i've been called with {play}")

    # Check if parameter has been sent
    if not name_or_url:
        await ctx.send("Please provide the path to a local MP3 file.")
        return

    # check if user sent youtube url for temp storage
    user_sent_youtube_url = is_youtube_url(name_or_url)
    if user_sent_youtube_url:
        file_path = f"{output_folder}/temp.mp3"
        await save_sound(ctx, "temp", name_or_url)
    else:
        file_path = f"{output_folder}/{name_or_url}.mp3"

    if os.path.exists(file_path):
        print(f"The file '{file_path}' exists.")
    else:
        print(f"The file '{file_path}' does not exist.")
        await ctx.send("You have not saved this sound yet.")
        return

    try:
        # Join the voice channel of the user who called the command
        channel = ctx.author.voice.channel
        vc = await channel.connect()

        # Play the saved MP3 file
        audio_source = FFmpegPCMAudio(file_path)
        vc.play(audio_source, after=lambda e: print(f'Done playing sound {name_or_url}.'))

        # Wait for the audio to finish playing
        while vc.is_playing():
            await asyncio.sleep(1)

        # Disconnect from the voice channel
        await vc.disconnect()
    except Exception as exception:
        print(exception)
        await ctx.send("An error occurred while processing your request.")

    # remove temp
    if user_sent_youtube_url:
        os.remove(file_path)


@bot.command(name="stop")
async def disconnect(ctx):
    # Check if the command author is in a voice channel
    if ctx.author.voice:
        # Get the voice channel the author is in
        voice_channel = ctx.author.voice.channel

        # Get the voice client for the bot in the server of the command author
        voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

        # Check if the bot is connected to a voice channel
        if voice_client and voice_client.is_connected():
            # Disconnect from the voice channel
            await voice_client.disconnect()
            await ctx.send(f"Disconnected from {voice_channel}.")
        else:
            await ctx.send("I'm not connected to a voice channel.")
    else:
        await ctx.send("You're not in a voice channel.")

bot.run(os.getenv("TOKEN"))
