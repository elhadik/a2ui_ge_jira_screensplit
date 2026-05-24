import os
import vertexai
from vertexai.agent_engines import AdkApp
from google.adk.apps import App
from agent import root_agent

adk_app = AdkApp(
    app=App(name='store_auditor_a2ui', root_agent=root_agent),
    enable_tracing=True,
)
