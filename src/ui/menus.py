import chainlit as cl

async def send_project_menu():
    actions = [
        cl.Action(name="select_project", payload={"id": "astroguido"}, label="🌌 AstroGuido"),
        cl.Action(name="select_project", payload={"id": "ai_office"}, label="🤖 AI Agent Office")
    ]
    await cl.Message(
        content="Выберите активный проект для работы:",
        actions=actions
    ).send()