from dataclasses import dataclass

from app.domain.errors import DomainError

SECTION_KEYS = ("completed", "decisions", "verification", "open_issues", "next_steps")


@dataclass(frozen=True)
class GeneratedDraft:
    sections: dict[str, str]
    citations: list[dict]
    warnings: list[str]


class DemoGenerator:
    def generate(self, snapshot: dict, mode: str = "normal") -> GeneratedDraft:
        if mode == "error":
            raise DomainError("GENERATION_FAILED", "演示生成器返回了受控错误", 500)
        if mode == "timeout":
            raise DomainError("GENERATION_TIMEOUT", "生成已达到等待上限，请重试或人工填写", 504)

        buckets: dict[str, list[str]] = {key: [] for key in SECTION_KEYS}
        citations: list[dict] = []
        keywords = {
            "verification": ("测试", "验证", "检查", "通过", "test"),
            "decisions": ("决定", "选择", "原因", "方案", "because"),
            "open_issues": ("问题", "阻塞", "失败", "风险", "待定", "未解决"),
            "next_steps": ("下一步", "建议", "后续", "todo", "待办"),
            "completed": ("完成", "实现", "提交", "合并", "修复"),
        }

        for material in snapshot.get("materials", []):
            content = material.get("content", "")
            for line_no, raw_line in enumerate(content.splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                lowered = line.lower()
                explicit_prefixes = (
                    ("已完成", "completed"),
                    ("完成", "completed"),
                    ("决定", "decisions"),
                    ("决策", "decisions"),
                    ("测试", "verification"),
                    ("验证", "verification"),
                    ("检查", "verification"),
                    ("遗留问题", "open_issues"),
                    ("问题", "open_issues"),
                    ("阻塞", "open_issues"),
                    ("下一步", "next_steps"),
                    ("建议", "next_steps"),
                    ("待办", "next_steps"),
                )
                section = next(
                    (
                        candidate
                        for prefix, candidate in explicit_prefixes
                        if lowered.startswith(prefix)
                    ),
                    "completed",
                )
                if section == "completed" and not lowered.startswith(("已完成", "完成")):
                    for candidate, words in keywords.items():
                        if any(word.lower() in lowered for word in words):
                            section = candidate
                            break
                buckets[section].append(line)
                citations.append(
                    {
                        "section": section,
                        "material_version_id": material["version_id"],
                        "start_line": line_no,
                        "end_line": line_no,
                        "quote": line[:4000],
                    }
                )

        labels = {
            "completed": "暂无材料说明已完成事项。",
            "decisions": "暂无材料说明关键决策及理由。",
            "verification": "未验证：材料中没有可定位的检查输出。",
            "open_issues": "未知：材料中没有明确的遗留问题。",
            "next_steps": "建议：请负责人补充下一步计划。",
        }
        sections = {
            key: "\n".join(f"• {item}" for item in values[:8]) if values else labels[key]
            for key, values in buckets.items()
        }
        if buckets["verification"] and not any(
            marker in " ".join(buckets["verification"]).lower()
            for marker in ("输出", "日志", "报告", "result", "passed")
        ):
            sections["verification"] = (
                "未验证：材料只有结论性描述，没有可定位的检查输出。\n" + sections["verification"]
            )
        return GeneratedDraft(
            sections=sections,
            citations=citations[:40],
            warnings=[] if snapshot.get("materials") else ["没有选中材料"],
        )
