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

    tool_emojis = {
        "read_file": "page_facing_up",
        "search_tool": "mag",
        "write_file": "pencil",
        "execute_bash": "desktop_computer",
        "execute_python_script": "snake",
        "handoff": "twisted_rightwards_arrows",
        "web_search_tavily": "globe_with_meridians",
        "crawl_website_firecrawl": "spider_web",
        "search_notion": "notebook",
        "read_notion_page": "notebook",
        "read_gmail_messages": "email",
        "send_gmail": "email",
        "draft_gmail": "email",
        "create_calendar_event": "calendar",
        "find_calendar_freebusy": "calendar",
        "search_drive_files": "file_folder",
        "modify_drive_permissions": "file_folder",
        "create_google_doc": "page_with_curl",
        "read_google_doc": "page_with_curl",
        "update_google_sheet": "bar_chart",
        "read_google_sheet": "bar_chart",
        "search_github_issues": "octocat",
        "create_github_issue": "octocat",
        "update_github_project_status": "octocat",
        "upload_to_s3": "package",
        "list_s3_bucket": "package",
        "send_slack_message": "speech_balloon",
        "list_slack_channels": "speech_balloon",
        "attach_file": "paperclip",
        "create_agent_post": "memo",
        "search_agent_posts": "memo",
        "list_past_conversations": "books",
        "read_conversation": "books",
        "railway_deploy": "rocket",
        "summarize_conversation": "brain",
        "update_user_profile": "brain",
        "subscribe_workspace_events": "bell",
        "manage_cloud_identity_groups": "bell",
        "generate_image": "art",
    }

    current_agent = "bark_bot"
    messages = [Message(role="user", content=augmented_text)]
    added_reactions = set()

    try:
        while True:
            # React to the user's original message with the active agent's emoji
            emoji = agent_emojis.get(current_agent, "robot_face")
            if emoji not in added_reactions:
                try:
                    await asyncio.to_thread(
                        slack_client.reactions_add,
                        channel=channel_id,
                        timestamp=event.get("ts"),
                        name=emoji
                    )
                    added_reactions.add(emoji)
                except SlackApiError:
                    pass  # Ignore if we already reacted with this emoji

            req = ChatRequest(
                messages=messages,
                user_id=f"slack_{user_id}",  # Prefix identity to avoid collision
                agent_id=current_agent
            )

            # Callback to stream intermediate LLM text to the user
            async def send_intermediate(text: str):
                try:
                    await asyncio.to_thread(
                        slack_client.chat_postMessage,
                        channel=channel_id,
                        text=text,
                        thread_ts=thread_ts
                    )
                except SlackApiError as e:
                    print(f"[Slack Error] Failed to post intermediate message: {e.response['error']}")

            # Callback to react with a tool-specific emoji when a tool is invoked
            async def on_tool_call(tool_name: str):
                emoji = tool_emojis.get(tool_name, "gear")
                if emoji not in added_reactions:
                    try:
                        await asyncio.to_thread(
                            slack_client.reactions_add,
                            channel=channel_id,
                            timestamp=event.get("ts"),
                            name=emoji
                        )
                        added_reactions.add(emoji)
                    except SlackApiError:
                        pass

            async with AsyncSessionLocal() as db:
                conversation_id = f"slack_thread_{thread_ts}"
                response = await handle_chat_request(req, db=db, conversation_id=conversation_id, on_intermediate_response=send_intermediate, on_tool_call=on_tool_call)
                
            final_text = response.message.content

            # Check if Orchestrator initiated a Handoff — skip posting the
            # internal routing message and loop to the target agent instead.
            if response.agent_id and response.agent_id != current_agent:
                current_agent = response.agent_id
                messages = []
                continue

            # If the LLM decided no reply is needed, silently exit
            if response.no_reply:
                break

            # Send the final response back to Slack
            try:
                await asyncio.to_thread(
                    slack_client.chat_postMessage,
                    channel=channel_id,
                    text=final_text,
                    thread_ts=thread_ts
                )
            except SlackApiError as e:
                print(f"[Slack Error] Failed to post message: {e.response['error']}")

            # Upload any file attachments natively into the thread
            if response.attachments:
                for att in response.attachments:
                    try:
                        await asyncio.to_thread(
                            slack_client.files_upload_v2,
                            channel=channel_id,
                            file=att.file_path,
                            filename=att.filename,
                            thread_ts=thread_ts
                        )
                    except Exception as att_err:
                        print(f"[Slack Error] Failed to upload attachment '{att.filename}': {att_err}")

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
    finally:
        # Remove any reaction emojis we added once processing is completely done
        for emoji in added_reactions:
            try:
                await asyncio.to_thread(
                    slack_client.reactions_remove,
                    channel=channel_id,
                    timestamp=event.get("ts"),
                    name=emoji
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
