import pytest
from actions.base_action import BaseAction

class ConcreteAction(BaseAction):
    async def execute(self, command: str, **kwargs) -> str:
        return f"executed: {command}"

def test_base_action_name():
    action = ConcreteAction({})
    assert action.name == "concreteaction"

def test_can_handle():
    action = ConcreteAction({})
    assert action.can_handle("concreteaction") is True
    assert action.can_handle("other") is False

@pytest.mark.asyncio
async def test_execute():
    action = ConcreteAction({})
    result = await action.execute("test command")
    assert result == "executed: test command"