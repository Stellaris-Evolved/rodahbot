import json

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
print(DISCORD_TOKEN)
# AWS DynamoDB client
dynamodb = boto3.client('dynamodb')

# Initialize the Discord bot
bot = commands.Bot(command_prefix='/')

# Define the set of words to count
words_to_count = ['bio hive', 'biohive', 'bio-hive', 'bio_hive']
TABLE_NAME = 'word_counts'
GUILD_ID = 871511987677442151
print(bot.get_guild(GUILD_ID))


@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user.name}')


@bot.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    # Update the DynamoDB table with the word counts and message IDs
    for word in words_to_count:
        count = message.content.lower().count(word)
        if count > 0:
            response = dynamodb.update_item(
                TableName=TABLE_NAME,
                Key={'word': {'S': 'biohive'}},
                # Using 'biohive' as the key for all variations
                UpdateExpression='SET #messages.#message_id = if_not_exists(#messages.#message_id, :zero) + :val',
                ExpressionAttributeNames={
                    '#messages': 'messages',
                    '#message_id': str(message.id),
                },
                ExpressionAttributeValues={
                    ':zero': {'N': '0'},
                    ':val': {'N': str(count)},
                }
            )

    # React to the message with a thumbs-up emoji
    await message.add_reaction('\U0001F44D')


@bot.slash_command(name='biohive-when')
async def biohive_when(ctx):
    # Retrieve the word counts from the DynamoDB table
    response = dynamodb.scan(TableName=TABLE_NAME)
    items = response.get('Items', [])

    # Create a response message with the word counts and message IDs
    counts = 0
    for item in items:
        messages = item.get('messages', {})
        for message_id, cnt in messages.items():
            counts += cnt["N"]

    # Send the response message
    await ctx.send(f"Biohive has been delayed {counts} weeks!")


# Create DynamoDB table if it doesn't exist
def create_table_if_not_exists():
    try:
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'word', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'word', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            # Table already exists
            return
        else:
            raise


async def fetch_and_populate_table():
    guild = bot.get_guild(GUILD_ID)  # Replace with your guild ID

    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            async for message in channel.history(limit=None):
                process_message(message)


# Process a message and update the table
def process_message(message):
    # Normalize and count the occurrences of words in the message
    word_counts = {}
    for word in words_to_count:
        count = message.content.lower().count(word)
        if count > 0:
            if word in word_counts:
                word_counts[word] += count
            else:
                word_counts[word] = count

    # Calculate the total count for all word variations
    total_count = sum(word_counts.values())

    # Update the table with the total count for all word variations
    response = dynamodb.update_item(
        TableName=TABLE_NAME,
        Key={'word': {'S': 'total_count'}},
        UpdateExpression='ADD message_ids :id SET #count = #count + :count',
        ExpressionAttributeNames={'#count': 'count'},
        ExpressionAttributeValues={
            ':id': {'SS': [message.id]},
            ':count': {'N': str(total_count)}
        },
        ReturnValues='ALL_NEW'
    )

    # Print the updated item
    print(response['Attributes'])


bot.run(DISCORD_TOKEN)
