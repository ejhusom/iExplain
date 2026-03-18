from __future__ import annotations

from iexplain.runtime.catalog import SkillLibrary


def test_skill_library_reads_frontmatter_and_renders_body(tmp_path):
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: demo-skill",
                "description: Demo skill for controlled testing.",
                "metadata:",
                "  owner: tests",
                '  version: "1"',
                "allowed-tools: Read Bash(git:*)",
                "---",
                "",
                "## Workflow",
                "",
                "1. Do the thing.",
            ]
        ),
        encoding="utf-8",
    )

    library = SkillLibrary(tmp_path)
    skill = library.get("demo-skill")

    assert skill.name == "demo-skill"
    assert skill.description == "Demo skill for controlled testing."
    assert skill.metadata == {"owner": "tests", "version": "1"}
    assert skill.allowed_tools == ["Read", "Bash(git:*)"]

    catalog = library.list_catalog()
    assert catalog["demo-skill"]["name"] == "demo-skill"
    assert catalog["demo-skill"]["description"] == "Demo skill for controlled testing."

    rendered = library.render(["demo-skill"])
    assert "Description: Demo skill for controlled testing." in rendered
    assert "## Workflow" in rendered
    assert "---" not in rendered
