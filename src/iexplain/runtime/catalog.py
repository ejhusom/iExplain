from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


@dataclass(frozen=True)
class SkillInfo:
    name: str
    path: Path
    description: str
    body: str
    metadata: dict[str, str] = field(default_factory=dict)
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: list[str] = field(default_factory=list)


class PromptCatalog:
    def __init__(self, prompts_dir: str | Path):
        self.prompts_dir = Path(prompts_dir)

    def get(self, role: str, variant: str = "default") -> str:
        path = self.prompts_dir / role / f"{variant}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {role}/{variant}")
        return path.read_text(encoding="utf-8").strip()

    def list_catalog(self) -> dict[str, list[str]]:
        catalog: dict[str, list[str]] = {}
        if not self.prompts_dir.exists():
            return catalog
        for role_dir in sorted(path for path in self.prompts_dir.iterdir() if path.is_dir()):
            variants = sorted(file.stem for file in role_dir.glob("*.md"))
            catalog[role_dir.name] = variants
        return catalog


class SkillLibrary:
    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)
        self._skills = self._load_skills()

    def _load_skills(self) -> dict[str, SkillInfo]:
        skills: dict[str, SkillInfo] = {}
        if not self.skills_dir.exists():
            return skills
        for skill_dir in sorted(path for path in self.skills_dir.iterdir() if path.is_dir()):
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.exists():
                continue
            content = skill_path.read_text(encoding="utf-8").strip()
            frontmatter, body = self._split_frontmatter(content)
            name = str(frontmatter.get("name") or skill_dir.name)
            description = str(frontmatter.get("description") or self._extract_summary(body or content))
            metadata = frontmatter.get("metadata")
            skills[skill_dir.name] = SkillInfo(
                name=name,
                path=skill_path,
                description=description,
                body=body or content,
                metadata=metadata if isinstance(metadata, dict) else {},
                license=self._coerce_optional_text(frontmatter.get("license")),
                compatibility=self._coerce_optional_text(frontmatter.get("compatibility")),
                allowed_tools=self._parse_allowed_tools(frontmatter.get("allowed-tools")),
            )
        return skills

    @staticmethod
    def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        lines = content.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}, content.strip()

        frontmatter_lines: list[str] = []
        body_start = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                body_start = index + 1
                break
            frontmatter_lines.append(line)

        if body_start is None:
            return {}, content.strip()

        return SkillLibrary._parse_frontmatter(frontmatter_lines), "\n".join(lines[body_start:]).strip()

    @staticmethod
    def _parse_frontmatter(lines: list[str]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        nested_key: str | None = None
        nested_map: dict[str, str] | None = None

        for raw_line in lines:
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue

            indent = len(raw_line) - len(raw_line.lstrip(" "))
            line = raw_line.strip()

            if indent and nested_key and nested_map is not None:
                key, separator, value = line.partition(":")
                if separator:
                    nested_map[key.strip()] = SkillLibrary._strip_scalar(value.strip())
                continue

            nested_key = None
            nested_map = None
            key, separator, value = line.partition(":")
            if not separator:
                continue

            key = key.strip()
            value = value.strip()
            if not value:
                nested_key = key
                nested_map = {}
                data[key] = nested_map
                continue

            data[key] = SkillLibrary._strip_scalar(value)

        return data

    @staticmethod
    def _strip_scalar(value: str) -> str:
        text = value.strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
            return text[1:-1]
        return text

    @staticmethod
    def _extract_summary(content: str) -> str:
        for paragraph in content.split("\n\n"):
            text = paragraph.strip()
            if not text or text.startswith("#"):
                continue
            return " ".join(text.split())
        return ""

    def get(self, name: str) -> SkillInfo:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"Unknown skill: {name}") from exc

    def render(self, names: list[str]) -> str:
        sections: list[str] = []
        for name in names:
            skill = self.get(name)
            header = f"## Skill: {skill.name}\nDescription: {skill.description}"
            sections.append(f"{header}\n\n{skill.body}".strip())
        return "\n\n".join(sections).strip()

    def list_catalog(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "name": skill.name,
                "path": str(skill.path),
                "description": skill.description,
                "metadata": skill.metadata,
            }
            for name, skill in self._skills.items()
        }

    @staticmethod
    def _parse_allowed_tools(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item for item in re.split(r"\s+", value.strip()) if item]
        return []

    @staticmethod
    def _coerce_optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
