import requests
from PIL import Image
from io import BytesIO
import discord
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from discord.ext import tasks
import tweepy
from dotenv import load_dotenv
import os

load_dotenv()  # This loads the variables from .env into the environment

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
USER_ID = int(os.getenv("USER_ID"))
GLIF_API_TOKEN = os.getenv("GLIF_API_TOKEN")
CONSUMER_KEY = os.getenv("CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

intents = discord.Intents.default()  # This sets up the default intents
intents.messages = True  # For accessing messages
intents.reactions = True  # For accessing reactions
intents.message_content = True  # If you need to access the content of messages

class MyClient(discord.Client):

    def __init__(self, *, intents):
        super().__init__(intents=intents)

    async def download_images(self, attachments):
        async with aiohttp.ClientSession() as session:
            for attachment in attachments:
                if attachment.url.split('?')[0].endswith(('png', 'jpg', 'jpeg', 'gif')):
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            with open(attachment.filename, 'wb') as f:
                                f.write(data)
                            print(f'Downloaded {attachment.filename}.')


    async def call_glif_api_async(self,topic: str, year: str, temperature: float, api_token: str):
        url = "https://simple-api.glif.app/clrt25smf0025niqsvrmz9ehc"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": [topic, year, str(temperature)]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if "error" in response_data:
                        print(f"Error: {response_data['error']}")
                        return None
                    else:
                        print(f"Output: {response_data.get('output')}")
                        return response_data.get('output')
                else:
                    print(f"Failed to call Glif API, status code: {response.status}")
                    return None


    async def download_and_split_image_async(self,image_url):
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    # Read the image content
                    image_data = await response.read()
                    image = Image.open(BytesIO(image_data))
                    
                    width, height = image.size
                    quarter_height = height // 4
                    
                    images = []
                    for i in range(4):
                        top = i * quarter_height
                        bottom = (i + 1) * quarter_height if i < 3 else height
                        images.append(image.crop((0, top, width, bottom)))
                    
                    for i, img in enumerate(images, start=1):
                        img.save(f'image_quarter_{i}.png')
                        print(f'Quarter {i} saved as image_quarter_{i}.png')
                else:
                    print(f"Failed to download the image, status code: {response.status}")

    
    async def send_images_discord(self,channel_id, bot_token):


        await client.login(bot_token)  # Log in the bot with the provided token

        channel = client.get_channel(int(channel_id))  # Get the channel object
        if channel:
            # Define the image paths
            image_paths = [
                'image_quarter_1.png',
                'image_quarter_2.png',
                'image_quarter_3.png',
                'image_quarter_4.png'
            ]

            # Prepare the files to be sent
            files = [discord.File(path) for path in image_paths]

            # Send the text message with all the images attached
            await channel.send(content="## For your consideration:", files=files)
        else:
            print('Channel not found.')

    async def process_and_send_images(self):
        # Load the month and year from the YAML file
        with open('month.yaml', 'r') as file:
            month_data = yaml.safe_load(file)
        current_month = month_data['month']
        current_year = month_data['year']

        # Convert month name to number (January -> 1, February -> 2, ...)
        month_number = list(month_name).index(current_month)

        # Increment the month
        month_number += 1
        if month_number > 12:  # If the month is December, roll over to January and increment the year
            month_number = 1
            current_year += 1

        # Convert the month number back to name
        new_month = month_name[month_number]

        # Save the incremented month and year back to the YAML file
        with open('month.yaml', 'w') as file:
            yaml.dump({'month': new_month, 'year': current_year}, file)
        
        channel = self.get_channel(CHANNEL_ID)
        await channel.send(f"**Options for {new_month}, {current_year}:**")
        # Use the new month and year in the API call
        for i in range(10):
            image_url = await self.call_glif_api_async("anything", f"{new_month}, {current_year}", 1.8, GLIF_API_TOKEN)
            if image_url:
                await self.download_and_split_image_async(image_url)
                await self.send_images_discord(CHANNEL_ID, BOT_TOKEN)


    async def post_tweets_with_media(self):

        file_paths = ['image_quarter_1.png', 'image_quarter_2.png', 'image_quarter_3.png', 'image_quarter_4.png']
        text_template = "({current_number}/{total_number})"
        # Twitter API credentials
        consumer_key = CONSUMER_KEY
        consumer_secret = CONSUMER_SECRET
        access_token = ACCESS_TOKEN
        access_token_secret = ACCESS_TOKEN_SECRET

        # Initialize Tweepy for both v1.1 and v2 APIs
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, access_token_secret)
        api_v1 = tweepy.API(auth)
        client = tweepy.Client(consumer_key=consumer_key, consumer_secret=consumer_secret,
                            access_token=access_token, access_token_secret=access_token_secret)

        loop = asyncio.get_event_loop()
        total_files = len(file_paths)
        previous_tweet_id = None

        for index, file_path in enumerate(file_paths, start=1):
            text = text_template.format(current_number=index, total_number=total_files)

            # Upload the media file using v1.1 API in a separate thread
            media = await loop.run_in_executor(None, lambda: api_v1.media_upload(file_path))
            media_id = media.media_id_string

            # Tweet parameters
            tweet_params = {
                "text": text,
                "media_ids": [media_id]
            }
            # If replying to a previous tweet, add 'in_reply_to_tweet_id'
            if previous_tweet_id is not None:
                tweet_params["in_reply_to_tweet_id"] = previous_tweet_id

            # Create a tweet with the media using v2 API in a separate thread
            response = await loop.run_in_executor(None, lambda: client.create_tweet(**tweet_params))
            previous_tweet_id = response.data["id"]

        return "Posted {} images".format(total_files)

    async def count_emojis_and_post(self, consumer_key, consumer_secret, access_token, access_token_secret):
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print('Channel not found.')
            return

        today = datetime.utcnow().date()        
        votes = {}
        unique_users = {}
        message_votes = {}
        
        async for message in channel.history(limit=100, after=datetime.utcnow() - timedelta(days=1)):
            if message.author.id == USER_ID and message.created_at.date() == today:
                unique_reactors = set()
                for reaction in message.reactions:
                    users = [user async for user in reaction.users()]
                    for user in users:
                        unique_reactors.add(user.id)
                message_votes[message.id] = len(unique_reactors)

        if message_votes:
            top_voted_message_id = max(message_votes, key=message_votes.get)
            top_voted_message = await channel.fetch_message(top_voted_message_id)
            print(f"The top-voted post is Message ID {top_voted_message_id} with {message_votes[top_voted_message_id]} unique votes.")
            await self.download_images(top_voted_message.attachments)        
            # Optionally, download images from the top-voted message
            image_urls = [attachment.url for attachment in top_voted_message.attachments if attachment.url.split('?')[0].endswith(('png', 'jpg', 'jpeg', 'gif'))]
            print("Image URLs from the top-voted message:", image_urls)
            await self.download_images(top_voted_message.attachments)
            tweet_response = await self.post_tweets_with_media()
            print(tweet_response)                        
        else:
            print("No votes received.")

    # Create a background task that runs every 60 seconds

    @tasks.loop(seconds=60)
    async def daily_task(self):
        # Check if current time is 9 PM
        if datetime.now().hour == 17 and datetime.now().minute == 00:
            print("It's 9 PM, time to process and send images")
            await self.process_and_send_images()

        if datetime.now().hour == 21 and datetime.now().minute == 00:
            await self.count_emojis_and_post()

    # The on_ready event runs when the bot starts and is ready to receive events
    async def on_ready(self):
        print(f"Logged in as {self.user}!")
        self.daily_task.start()

client = MyClient(intents=intents)
client.run(BOT_TOKEN)
