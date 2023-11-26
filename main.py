import asyncio
from pytube import YouTube
from discord import FFmpegPCMAudio
import os
import discord
from discord.ext import commands

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
async def play_sound(ctx, name):
    print("i've been called with {play}")

    # Check if the file path is provided
    if not name:
        await ctx.send("Please provide the path to a local MP3 file.")
        return

    file_path = f"{output_folder}/{name}.mp3"
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
        vc.play(audio_source, after=lambda e: print(f'Done playing sound {name}.'))

        # Wait for the audio to finish playing
        while vc.is_playing():
            await asyncio.sleep(1)

        # Say done
        await ctx.send(f"Done playing {name}.")
        # Disconnect from the voice channel
        await vc.disconnect()
    except Exception as exception:
        print(exception)
        await ctx.send("An error occurred while processing your request.")

bot.run("")
