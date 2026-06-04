import logging
import re
import json
import uuid
from typing import List

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState, TextPart, DataPart, UnsupportedOperationError, Message, Role, Part
from a2a.utils.errors import ServerError

try:
    from a2a.utils import new_agent_parts_message
except ImportError:
    def new_agent_parts_message(parts, context_id, task_id):
        return Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=parts,
        )

from google.adk.runners import Runner
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

try:
    from .agent import get_agent
except ImportError:
    from agent import get_agent

logger = logging.getLogger(__name__)

A2UI_MIME_TYPE = "application/json+a2ui"
A2UI_OPEN_TAG = "<a2ui-json>"
A2UI_CLOSE_TAG = "</a2ui-json>"

_A2UI_BLOCK_RE = re.compile(
    f"{re.escape(A2UI_OPEN_TAG)}(.*?){re.escape(A2UI_CLOSE_TAG)}", re.DOTALL
)

def _sanitize_json(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```json"):
        s = s[len("```json"):]
    elif s.startswith("```"):
        s = s[len("```"):]
    if s.endswith("```"):
        s = s[:-len("```")]
    # Strip line-continuation backslashes before newlines
    s = re.sub(r'\\\s*\n', '\n', s)
    return s.strip()

def _create_a2ui_part(data: dict) -> Part:
    return Part(root=DataPart(data=data, metadata={"mimeType": A2UI_MIME_TYPE}))

def parse_response_to_parts(content: str) -> List[Part]:
    matches = list(_A2UI_BLOCK_RE.finditer(content))
    if not matches:
        clean = content.strip()
        return [Part(root=TextPart(text=clean))] if clean else []
    parts: List[Part] = []
    last_end = 0
    for match in matches:
        start, end = match.span()
        text_before = content[last_end:start].strip()
        if text_before:
            parts.append(Part(root=TextPart(text=text_before)))
        try:
            json_str = _sanitize_json(match.group(1))
            payload = json.loads(json_str)
            if isinstance(payload, list):
                for item in payload:
                    parts.append(_create_a2ui_part(item))
            else:
                parts.append(_create_a2ui_part(payload))
        except Exception as e:
            logger.error(f"Failed to parse A2UI JSON block: {e}")
        last_end = end
    trailing = content[last_end:].strip()
    if trailing:
        parts.append(Part(root=TextPart(text=trailing)))
    return parts

class StoreAuditorExecutor(AgentExecutor):
    def __init__(self):
        self.agent = None
        self.runner = None

    def _init_agent(self):
        if self.agent is None:
            self.agent = get_agent()
            self.runner = Runner(
                app_name="StoreInvoiceAuditorAgent",
                agent=self.agent,
                artifact_service=InMemoryArtifactService(),
                session_service=InMemorySessionService(),
                memory_service=InMemoryMemoryService(),
            )
            logger.info("StoreAuditorExecutor initialized runner")

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        self._init_agent()

        from a2a.contrib.tasks.vertex_task_converter import to_stored_part
        
        runner_parts = []
        if context.message and context.message.parts:
            for part in context.message.parts:
                try:
                    runner_parts.append(to_stored_part(part))
                except Exception as e:
                    logger.warning(f"Failed to convert part: {e}")

        if not runner_parts:
            query = context.get_user_input()
            runner_parts.append(types.Part(text=query))

        logger.info(f"StoreAuditorExecutor executing query with {len(runner_parts)} parts")

        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.submit()
        await updater.start_work()

        try:
            session = await self.runner.session_service.get_session(
                app_name=self.runner.app_name,
                user_id='user',
                session_id=context.context_id,
            )
            if session is None:
                session = await self.runner.session_service.create_session(
                    app_name=self.runner.app_name,
                    user_id='user',
                    state={},
                    session_id=context.context_id,
                )

            content = types.Content(role='user', parts=runner_parts)

            async for event in self.runner.run_async(
                session_id=session.id,
                user_id='user',
                new_message=content
            ):
                if hasattr(event, 'is_final_response') and event.is_final_response():
                    logger.info(f"[DEBUG] Final Event: {event} | Content: {getattr(event, 'content', None)}")
                    answer_text = ""
                    if event.content and event.content.parts:
                        answer_text = "\n".join(
                            [part.text for part in event.content.parts if part.text]
                        )

                    if answer_text:
                        final_parts = parse_response_to_parts(answer_text)
                        
                        # Self-healing: check if we have A2UI parts. If not, programmatically append the dashboard!
                        has_a2ui = any(
                            isinstance(part.root, DataPart) and part.root.metadata.get("mimeType") == A2UI_MIME_TYPE
                            for part in final_parts
                        )
                        if not has_a2ui:
                            logger.info("No A2UI dashboard component successfully parsed from LLM text response. Self-healing on the backend...")
                            try:
                                try:
                                    from .components import _LAST_ANALYSIS_RESULTS, generate_audit_a2ui_dashboard_tool
                                except ImportError:
                                    from components import _LAST_ANALYSIS_RESULTS, generate_audit_a2ui_dashboard_tool
                                if _LAST_ANALYSIS_RESULTS:
                                    logger.info(f"Self-healing: Found cached analysis results for merchant: {_LAST_ANALYSIS_RESULTS.get('merchant_name')}. Rebuilding dashboard A2UI block...")
                                    a2ui_block = generate_audit_a2ui_dashboard_tool("")
                                    # Strip tag wrapper
                                    if a2ui_block.startswith("<a2ui-json>"):
                                        a2ui_block = a2ui_block[len("<a2ui-json>"):].strip()
                                    if a2ui_block.endswith("</a2ui-json>"):
                                        a2ui_block = a2ui_block[:-len("</a2ui-json>")].strip()
                                    
                                    payload = json.loads(a2ui_block)
                                    if isinstance(payload, list):
                                        for item in payload:
                                            final_parts.append(_create_a2ui_part(item))
                                    else:
                                        final_parts.append(_create_a2ui_part(payload))
                                    logger.info("✓ Self-healed: Programmatically appended visual A2UI dashboard part to final parts!")
                                else:
                                    logger.warning("Unable to self-heal: _LAST_ANALYSIS_RESULTS cache is empty.")
                            except Exception as a2ui_err:
                                logger.error(f"Failed to programmatically append A2UI dashboard: {a2ui_err}")

                        await updater.update_status(
                            TaskState.completed,
                            new_agent_parts_message(
                                final_parts,
                                context.context_id,
                                context.task_id,
                            ),
                            final=True,
                        )
                    else:
                        await updater.update_status(
                            TaskState.completed,
                            new_agent_parts_message(
                                [Part(root=TextPart(text="No response generated."))],
                                context.context_id,
                                context.task_id,
                            ),
                            final=True,
                        )
                    break
        except Exception as e:
            logger.error(f"Error in StoreAuditorExecutor: {e}", exc_info=True)
            await updater.update_status(
                TaskState.failed,
                message=Message(
                    message_id=str(uuid.uuid4()),
                    role=Role.agent,
                    parts=[TextPart(text=f"An error occurred: {str(e)}")]
                )
            )
            raise
        finally:
            pass

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        raise ServerError(error=UnsupportedOperationError())
