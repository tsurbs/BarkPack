import os
import asyncio
import traceback
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from slack_sdk.signature import SignatureVerifier
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from app.core.orchestrator import handle_chat_request
from app.models.schemas import ChatRequest, Message
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/slack", tags=["Slack Surface"])

# Load Slack Secrets from Env
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Initialize WebClient for sending messages back
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Initialize verifier to ensure requests are actually from Slack
signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET) if SLACK_SIGNING_SECRET else None

async def process_slack_message(event: dict):
    """
    Background task to process the message and send the response back to Slack.
    Uses the thread_ts if available so bot replies stay in thread.
    """
    channel_id = event.get("channel")
    user_id = event.get("user")
    text = event.get("text", "")
    thread_ts = event.get("thread_ts") or event.get("ts")  # Reply in thread if it exists, otherwise start one
    
    # We append formatting instructions directly to the user's message so the agent knows it's acting in Slack
    slack_formatting_instruction = (
        "\n\n[System Note: You are currently responding to the user inside Slack. "
        "DO NOT use standard markdown like **bold** or # headings. "
        "Slack requires pseudo-markdown: *bold*, _italics_, ~strikethrough~, `code`, and triple-backticks for blockquotes/codeblocks. "
        "Structure your response so it looks beautiful in Slack.]"
    )
    augmented_text = text + slack_formatting_instruction

    agent_emojis = {
        "bark_bot": "dog",
        "data_analyst": "chart_with_upwards_trend",
        "software_engineer": "computer",
        "google_workspace": "date",
        "knowledge_retriever": "brain",
        "project_manager": "clipboard",
        "memory_summarizer": "floppy_disk"
    }

    current_agent = "bark_bot"
    messages = [Message(role="user", content=augmented_text)]

    try:
        while True:
            # React to the user's original message with the active agent's emoji
            emoji = agent_emojis.get(current_agent, "robot_face")
            try:
                await asyncio.to_thread(
                    slack_client.reactions_add,
                    channel=channel_id,
                    timestamp=event.get("ts"),
                    name=emoji
                )
            except SlackApiError:
                pass  # Ignore if we already reacted with this emoji

            req = ChatRequest(
                messages=messages,
                user_id=f"slack_{user_id}",  # Prefix identity to avoid collision
                agent_id=current_agent
            )

            # Resolve Orchestrator with a DB Session
            async with AsyncSessionLocal() as db:
                # Note: We generate a deterministic conversation ID based on the Slack thread_ts 
                # so that subsequent replies in the same thread are chunked into the same DB Conversation.
                conversation_id = f"slack_thread_{thread_ts}"
                response = await handle_chat_request(req, db=db, conversation_id=conversation_id)
                
            final_text = response.message.content
            
            # Send message back to Slack Async
            try:
                # We must use asyncio.to_thread because the slack_sdk webclient is currently synchronous here
                await asyncio.to_thread(
                    slack_client.chat_postMessage,
                    channel=channel_id,
                    text=final_text,
                    thread_ts=thread_ts
                )
            except SlackApiError as e:
                print(f"[Slack Error] Failed to post message: {e.response['error']}")

            # Check if Orchestrator initiated a Handoff
            if response.agent_id and response.agent_id != current_agent:
                current_agent = response.agent_id
                messages = []  # Clear messages for the new agent context so we don't duplicate the initial prompt
                continue
            else:
                break

    except Exception as e:
        print(f"[Slack Error] Internal Server Error during message processing:")
        traceback.print_exc()
        error_text = f"🚨 *System Error*: I encountered a critical fault while processing your request: `{str(e)}`"
        try:
            await asyncio.to_thread(
                slack_client.chat_postMessage,
                channel=channel_id,
                text=error_text,
                thread_ts=thread_ts
            )
        except SlackApiError:
            pass


@router.post("/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Receives events from the Slack Events API.
    Must respond within 3 seconds to avoid Slack retries, so processing is offloaded to a BackgroundTask.
    """
    body = await request.body()
    headers = request.headers
    
    # Verify signature if secret is provided in environment
    if signature_verifier:
        if not signature_verifier.is_valid_request(body, headers):
            raise HTTPException(status_code=401, detail="Invalid Request Signature")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Handle Slack URL verification challenge
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Process Event Callbacks
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        
        # We only care about `message` events that are NOT from bots
        if event.get("type") == "message" and "bot_id" not in event:
            # Ignore message edit/delete/hidden events
            if event.get("subtype"):
                return {"status": "ignored"}
                
            # Offload heavy LLM reasoning to background task so we ACK Slack immediately
            background_tasks.add_task(process_slack_message, event)

    return {"status": "ok"}
