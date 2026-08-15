import logging

logger = logging.getLogger("ui_utils")

class SafeStep:
    """
    Класс-заглушка для cl.Step, который позволяет коду работать 
    как в Chainlit, так и в обычном FastAPI/CLI режиме.
    """
    def __init__(self, name, type="run"):
        self.name = name
        self.type = type
        self.input = None
        self.output = None
        
        # Инициализируем флаг сразу, чтобы избежать проблем с __setattr__
        self._is_chainlit = False
        
        try:
            import chainlit as cl
            self.cl = cl
            self.real_step = cl.Step(name=name, type=type)
            self._is_chainlit = True
        except Exception:
            logger.info(f"[SafeStep] Работа в режиме без Chainlit. Шаг '{name}' будет проигнорирован.")

    @property
    def is_chainlit(self):
        return self._is_chainlit

    async def send(self):
        if self.is_chainlit:
            try:
                await self.real_step.send()
            except Exception as e:
                logger.error(f"Ошибка cl.Step.send: {e}")
        return self

    def update(self):
        if self.is_chainlit:
            try:
                self.real_step.update()
            except Exception as e:
                logger.error(f"Ошибка cl.Step.update: {e}")

    async def aupdate(self):
        if self.is_chainlit:
            try:
                await self.real_step.update()
            except Exception as e:
                logger.error(f"Ошибка cl.Step.aupdate: {e}")

    def set_output(self, value):
        self.output = value
        if self.is_chainlit:
            try:
                self.real_step.output = value
            except Exception as e:
                logger.error(f"Ошибка установки output в cl.Step: {e}")
