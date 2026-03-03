import os
import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.tools.base import BaseTool
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

class SendSlackMessageArgs(BaseModel):
    channel_id: str = Field(description="The internal Slack Channel ID (e.g. C01234567) to send the message to. You must use the ID, not the #name.")
    message: str = Field(description="The text content of the message to send.")

class SendSlackMessageTool(BaseTool):
    name = "send_slack_message"
    description = "Send a message to any Slack channel the bot has access to using the channel ID."
    args_schema = SendSlackMessageArgs

    async def run(self, args: SendSlackMessageArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            return "Error: SLACK_BOT_TOKEN not configured."
        
        client = WebClient(token=token)
        try:
            response = await asyncio.to_thread(
                client.chat_postMessage,
                channel=args.channel_id,
                text=args.message
            )
            return f"Successfully sent message to {args.channel_id}."
        except SlackApiError as e:
            return f"Slack API Error: {e.response['error']}"


class ListSlackChannelsArgs(BaseModel):
    pass

class ListSlackChannelsTool(BaseTool):
    name = "list_slack_channels"
    description = "List all public Slack channels the bot can see. Useful for getting a channel ID before sending a message."
    args_schema = ListSlackChannelsArgs

    async def run(self, args: ListSlackChannelsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        token = os.getenv("SLACK_BOT_TOKEN")
        if not token:
            return "Error: SLACK_BOT_TOKEN not configured."
        
        client = WebClient(token=token)
        try:
            response = await asyncio.to_thread(
                client.conversations_list,
                types="public_channel"
            )
            channels = response.get("channels", [])
            output = ""
            for c in channels:
                output += f"#{c['name']} (ID: {c['id']})\n"
            return output if output else "No channels found."
        except SlackApiError as e:
            return f"Slack API Error: {e.response['error']}"
