import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Set up paths to locate the agents package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue
from executor import StoreAuditorExecutor
from a2a.types import Message, Role, Part, TextPart, MessageSendParams

# Configure logging to show tool execution logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    load_dotenv()
    
    # Ensure required credentials are set
    if not os.environ.get("PROJECT_ID") or not os.environ.get("JIRA_API_TOKEN"):
        print("Warning: Missing PROJECT_ID or JIRA_API_TOKEN. Please ensure your .env file is loaded.")

    print("Initializing StoreAuditorExecutor...")
    executor = StoreAuditorExecutor()

    # Path to your local sample invoice inside the assets folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sample_invoice_path = os.path.abspath(os.path.join(script_dir, "../assets/sample_invoice.png"))
    
    if not os.path.exists(sample_invoice_path):
        print(f"Error: Sample invoice not found at {sample_invoice_path}")
        return

    # Mock the user request passing the invoice file path
    user_message = Message(
        message_id="test-msg-id",
        role=Role.user,
        parts=[Part(root=TextPart(text=f"Run the store audit and show me the expense breakdown chart for the invoice at {sample_invoice_path}"))]
    )

    request_params = MessageSendParams(message=user_message)
    context = RequestContext(
        context_id="test-session-123",
        task_id="test-task-456",
        request=request_params
    )
    
    event_queue = EventQueue()

    print("\n--- STARTING LOCAL AGENT EXECUTION ---")
    try:
        await executor.execute(context, event_queue)
        print("--- AGENT EXECUTION COMPLETED ---")
    except Exception as e:
        print(f"\nExecution failed with error: {e}")
        return

    # Inspect generated events
    print("\n--- PARSING FINAL A2UI OUTPUT PARTS ---")
    try:
        while True:
            event = event_queue.queue.get_nowait()
            print(f"Event received: Type={type(event)}")
            if hasattr(event, "task_status"):
                print(f"  - state: {event.task_status.state.name}")
                if event.task_status.message:
                    parts = event.task_status.message.parts
                    for idx, part in enumerate(parts):
                        if hasattr(part.root, "text"):
                            print(f"    [Part {idx} (Text)]:\n{part.root.text}")
                        elif hasattr(part.root, "data"):
                            import pprint
                            print(f"    [Part {idx} (A2UI Component)]:")
                            pprint.pprint(part.root.data)
            else:
                print(f"  - Details: {event}")
    except asyncio.QueueEmpty:
        pass
        pass

if __name__ == "__main__":
    asyncio.run(main())
