import discord
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import re

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('discord_token')
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    voice_clients = {}
    queues = {}  # Hàng chờ cho từng server
    yt_dl_options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "default_search": "ytsearch",
        "quiet": True
    }
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn -filter:a "volume=0.25"'}

    def is_url(input_str):
        return re.match(r'https?://[^\s]+', input_str) is not None

    async def connect_voice_channel(message):
        voice_client = voice_clients.get(message.guild.id)
        user_channel = message.author.voice.channel

        if not voice_client:
            voice_client = await user_channel.connect()
            voice_clients[message.guild.id] = voice_client
        elif voice_client.is_connected() and voice_client.channel != user_channel:
            await voice_client.move_to(user_channel)
        return voice_client

    def play_next_song(guild_id):
        if queues[guild_id]:
            next_song = queues[guild_id].pop(0)
            voice_clients[guild_id].play(next_song['player'], after=lambda e: play_next_song(guild_id))
            asyncio.run_coroutine_threadsafe(
                next_song['message'].channel.send(f"Now playing **{next_song['title']}**\nLink: {next_song['webpage_url']}"),
                client.loop
            )

    @client.event
    async def on_ready():
        print(f'{client.user} is now online and ready to jam!')

    @client.event
    async def on_message(message):
        if message.author.bot:
            return

        if message.content.startswith("?play"):
            query = " ".join(message.content.split()[1:])
            if not query:
                await message.channel.send("Please provide a song name or URL.")
                return

            try:
                # Kết nối với voice channel
                voice_client = await connect_voice_channel(message)

                # Tải thông tin bài hát
                if is_url(query):
                    data = ytdl.extract_info(query, download=False)
                else:
                    data = ytdl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]

                song_url = data['url']
                title = data.get('title', 'Unknown Title')
                webpage_url = data.get('webpage_url', 'URL not available')
                player = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)

                # Thêm bài hát vào hàng chờ
                if message.guild.id not in queues:
                    queues[message.guild.id] = []

                queues[message.guild.id].append({
                    'player': player,
                    'title': title,
                    'webpage_url': webpage_url,
                    'message': message
                })

                # Nếu không có bài hát nào đang phát, phát bài đầu tiên
                if not voice_client.is_playing():
                    play_next_song(message.guild.id)
                    await message.channel.send(f"Started playing **{title}**\nLink: {webpage_url}")
                else:
                    await message.channel.send(f"Added to queue: **{title}**\nLink: {webpage_url}")

            except Exception as e:
                print(f"Error: {e}")
                await message.channel.send("An error occurred while trying to play the song.")

        elif message.content.startswith("?pause"):
            voice_client = voice_clients.get(message.guild.id)
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                await message.channel.send("Song paused.")
            else:
                await message.channel.send("No song is currently playing.")

        elif message.content.startswith("?resume"):
            voice_client = voice_clients.get(message.guild.id)
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await message.channel.send("Song resumed.")
            else:
                await message.channel.send("No song is currently paused.")

        elif message.content.startswith("?stop"):
            voice_client = voice_clients.get(message.guild.id)
            if voice_client:
                queues[message.guild.id] = []  # Xóa hàng chờ
                voice_client.stop()
                await voice_client.disconnect()
                await message.channel.send("Playback stopped and disconnected from the voice channel.")
            else:
                await message.channel.send("Bot is not connected to a voice channel.")

        elif message.content.startswith("?list"):
            if message.guild.id in queues and queues[message.guild.id]:
                queue_list = [f"{idx + 1}. **{song['title']}**" for idx, song in enumerate(queues[message.guild.id])]
                queue_message = "\n".join(queue_list)
                await message.channel.send(f"**Queue List:**\n{queue_message}")
            else:
                await message.channel.send("The queue is currently empty.")

    client.run(TOKEN)
