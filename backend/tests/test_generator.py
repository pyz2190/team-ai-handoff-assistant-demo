import pytest

from app.domain.errors import DomainError
from app.generator import DemoGenerator

SNAPSHOT = {
    "task": {"title": "任务", "goal": "目标", "acceptance_criteria": "验收"},
    "materials": [
        {
            "version_id": "v1",
            "content": (
                "已完成接口。\n决定：使用事务。\n测试：18 passed。\n"
                "遗留问题：窄屏错位。\n下一步：修复样式。"
            ),
        }
    ],
}


def test_generator_is_deterministic_and_cited():
    generator = DemoGenerator()
    first = generator.generate(SNAPSHOT)
    second = generator.generate(SNAPSHOT)
    assert first == second
    assert all(first.sections.values())
    assert {item["section"] for item in first.citations} >= {
        "completed",
        "decisions",
        "verification",
        "open_issues",
        "next_steps",
    }
    assert "已完成接口" in first.sections["completed"]
    assert "使用事务" in first.sections["decisions"]
    assert "18 passed" in first.sections["verification"]
    assert "窄屏错位" in first.sections["open_issues"]
    assert "修复样式" in first.sections["next_steps"]


@pytest.mark.parametrize("mode,status", [("error", 500), ("timeout", 504)])
def test_generator_controlled_failure(mode, status):
    with pytest.raises(DomainError) as caught:
        DemoGenerator().generate(SNAPSHOT, mode)
    assert caught.value.status_code == status
