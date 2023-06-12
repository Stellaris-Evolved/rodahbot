import json
import re
from datetime import datetime
from time import sleep

import boto3
import discord
from botocore.exceptions import ClientError
from discord.ext import commands


def get_secret():
    secret_name = "rodahbot/discord_token"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    return json.loads(get_secret_value_response['SecretString'])

    # Your code goes here.


# Discord bot token
DISCORD_TOKEN = get_secret()['DISCORD_TOKEN']
# AWS DynamoDB client
dynamodb = boto3.client('dynamodb')
# Initialize the Discord bot
bot = commands.Bot(command_prefix='/', intents=discord.Intents.all())

# Define the set of words to count

words = ['biohive', 'bioswarm', 'biologicalhive', 'biologicalhivemind',
         'biologicalswarm']
word_regex = re.compile(
    '|'.join([
        '(' + word + ')'
        for word in words
    ]),  re.A | re.I
)

TABLE_NAME = 'word_counts'
GUILD_ID = 871511987677442151

@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user.name}')
    create_table_if_not_exists()
    await fetch_and_populate_table()


# Create DynamoDB table if it doesn't exist
def create_table_if_not_exists():
    try:
        response = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'id', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )

        sleep(3)

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            # Table already exists
            return
        else:
            raise


async def fetch_and_populate_table():
    pass
    # guild = bot.get_guild(GUILD_ID)  # Replace with your guild ID
    # count = 0
    # for channel in guild.channels:
    #     print(channel.name)
    #     if isinstance(channel, discord.TextChannel):
    #         async for message in channel.history(limit=None):
    #             count = count_words(message.content)
    #
    # dynamodb.update_item(
    #     TableName=TABLE_NAME,
    #     Key={'id': {'S': 'total_count'}},
    #     UpdateExpression='SET message_count = if_not_exists(message_count, :zero) + :val',
    #     ExpressionAttributeValues={
    #         ':zero': {'N': '0'},
    #         ':val': {'N': str(count)}
    #     }
    # )


def count_words(message: str):
    return len(re.findall(word_regex, ''.join(filter(str.isalnum, message))))


# Process a message and update the table
def process_message(message: discord.Message):
    # Normalize and count the occurrences of words in the message
    count = count_words(message.content)

    if count:
        print(message.content)
        # Update the table with the total count for all word variations
        dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={'id': {'S': 'total_count'}},
            UpdateExpression='SET total_count = if_not_exists(total_count, :zero) + :val',
            ExpressionAttributeValues={
                ':zero': {'N': '0'},
                ':val': {'N': str(count)}
            }
        )


@bot.event
async def on_message(message: discord.Message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return
    count = count_words(message.content)

    if count > 0:
        print(message)
        response = dynamodb.update_item(
            TableName=TABLE_NAME,
            Key={'id': {'S': 'total_count'}},
            UpdateExpression='SET total_count = if_not_exists(total_count, :zero) + :val',
            ExpressionAttributeValues={
                ':zero': {'N': '0'},
                ':val': {'N': str(count)}
            }
        )

        # React to the message with a thumbs-up emoji
        await message.add_reaction("<:when:962431720660025354>")
    if 'when' in message.content and count:
        response = dynamodb.scan(TableName=TABLE_NAME)
        counts = response.get('Items', [])[0]['total_count']['N']

        # Send the response message
        await message.channel.send(f"Biohive has been delayed {counts} weeks!")


@bot.slash_command(name='biohive-when')
async def biohive_when(ctx: discord.ApplicationContext):
    # Retrieve the word counts from the DynamoDB table
    response = dynamodb.scan(TableName=TABLE_NAME)
    counts = response.get('Items', [])[0]['total_count']['N']

    # Send the response message
    await ctx.respond(f"Biohive has been delayed {counts} weeks!")


bot.run(DISCORD_TOKEN)
