from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SKILLS_DIR = Path(__file__).resolve().parent / "skills"
FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

VISIT_KEYWORDS = (
    "recent visit",
    "latest visit",
    "visit summary",
    "最近",
    "最新",
    "就诊",
    "复诊",
)
CASE_KEYWORDS = (
    "medical case",
    "diagnosis",
    "case summary",
    "病历",
    "病例",
    "诊断",
    "治疗",
)
IDENTITY_KEYWORDS = (
    "patient",
    "patient code",
    "phone",
    "id number",
    "患者",
    "身份证",
    "手机号",
)


@dataclass(frozen=True)
class DomainSkillBundle:
    name: str
    description: str
    content: str


class DomainSkillLoader:
    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir
        self._bundles = self._load_bundles()

    def load(self, name: str) -> DomainSkillBundle:
        bundle = self._bundles.get(name)
        if bundle is None:
            raise KeyError(f"Unknown domain skill: {name}")
        return bundle

    def select_for_request(
        self,
        *,
        user_query: str,
        has_images: bool,
        memory_context: dict | None,
        current_patient_context: dict | None,
    ) -> list[DomainSkillBundle]:
        lowered = user_query.lower()
        selected: list[str] = []

        if current_patient_context or any(keyword in lowered for keyword in IDENTITY_KEYWORDS):
            selected.append("identity-verification")
        if any(keyword in lowered for keyword in VISIT_KEYWORDS):
            selected.append("visit-summary")
        if any(keyword in lowered for keyword in CASE_KEYWORDS):
            selected.append("medical-case-query")
        if has_images:
            selected.append("image-reasoning")
        if memory_context and (
            memory_context.get("short_term_memories")
            or memory_context.get("user_profile")
            or memory_context.get("relevant_events")
        ):
            selected.append("memory-usage")

        return [self.load(name) for name in selected]

    def _load_bundles(self) -> dict[str, DomainSkillBundle]:
        bundles: dict[str, DomainSkillBundle] = {}
        for path in sorted(self.skills_dir.glob("*.md")):
            raw_text = path.read_text(encoding="utf-8").strip()
            frontmatter, body = self._split_frontmatter(raw_text)
            name = frontmatter.get("name", path.stem)
            bundles[name] = DomainSkillBundle(
                name=name,
                description=frontmatter.get("description", ""),
                content=body,
            )
        return bundles

    def _split_frontmatter(self, text: str) -> tuple[dict[str, str], str]:
        match = FRONTMATTER_PATTERN.match(text)
        if not match:
            return {}, text

        frontmatter: dict[str, str] = {}
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip().strip('"')
        return frontmatter, match.group(2).strip()
