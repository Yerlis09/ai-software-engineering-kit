"""Load the kit catalog (profiles, technologies, databases...) and resolve a selection.

All of it is data (JSON + Markdown) so teams extend the kit by adding files, not code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_project.context_index import load_routing
from ai_project.errors import EXIT_USAGE, KitError

UNDECIDED = "undecided"
# Deployment choices that keep deployment out of the project's scope: no serving stack
# (NGINX) and no ``deploy/`` folder are added until deployment is requested.
OUT_OF_SCOPE_DEPLOYMENTS = ("none", UNDECIDED)

PROFILE_ORDER = (
    "backend-api",
    "frontend",
    "fullstack",
    "python-automation",
    "data-engineering",
    "microservice",
    "custom",
)


@dataclass(frozen=True)
class Option:
    key: str
    title: str
    stacks: tuple[str, ...] = ()
    language: str = "TODO"
    framework: str = "TODO"
    serving_stacks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Profile:
    name: str
    title: str
    description: str
    agents: tuple[str, ...]
    agents_if_database: tuple[str, ...]
    rules: tuple[str, ...]
    workflows: tuple[str, ...]
    technologies: tuple[str, ...]
    stacks: tuple[str, ...]
    template: str
    structure: tuple[str, ...]


@dataclass(frozen=True)
class Selection:
    """What the developer chose. Stored in the lock file and replayed by ``update``."""

    profile: str
    technology: str
    database: str
    deployment: str
    assistants: tuple[str, ...]
    extra_stacks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "technology": self.technology,
            "database": self.database,
            "deployment": self.deployment,
            "assistants": list(self.assistants),
            "extra_stacks": list(self.extra_stacks),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Selection:
        try:
            return cls(
                profile=str(data["profile"]),
                technology=str(data["technology"]),
                database=str(data["database"]),
                deployment=str(data["deployment"]),
                assistants=tuple(str(a) for a in data.get("assistants", [])),
                extra_stacks=tuple(str(s) for s in data.get("extra_stacks", [])),
            )
        except (KeyError, TypeError) as exc:
            raise KitError(f"Invalid selection in lock file: {exc}") from None


@dataclass(frozen=True)
class Resolved:
    """The concrete set of kit content a selection maps to."""

    profile: Profile
    agents: tuple[str, ...]
    rules: tuple[str, ...]
    workflows: tuple[str, ...]
    stacks: tuple[str, ...]
    assistants: tuple[str, ...] = field(default=())
    structure: tuple[str, ...] = field(default=())


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KitError(f"Cannot read kit file {path}: {exc}") from None


def deployment_in_scope(deployment: str) -> bool:
    """Whether the selected deployment brings deployment content into the project."""
    return deployment not in OUT_OF_SCOPE_DEPLOYMENTS


def _is_deploy_dir(directory: str) -> bool:
    return directory == "deploy" or directory.startswith("deploy/")


def _unique(items) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


class Catalog:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.organization: dict[str, str] = {
            k: str(v) for k, v in _load_json(root / "catalog" / "organization.json").items()
        }
        self.technologies = self._load_options("technologies")
        self.databases = self._load_options("databases")
        self.deployments = self._load_options("deployments")
        self.assistants = self._load_options("assistants")
        self.profiles = self._load_profiles()
        self._routing: dict[str, Any] | None = None

    @property
    def routing(self) -> dict[str, Any]:
        """Context routing metadata (``catalog/context.json``), validated on first use."""
        if self._routing is None:
            self._routing = load_routing(self.root)
        return self._routing

    def _load_options(self, name: str) -> dict[str, Option]:
        data = _load_json(self.root / "catalog" / f"{name}.json")
        return {
            key: Option(
                key,
                str(value["title"]),
                tuple(value.get("stacks", [])),
                str(value.get("language", "TODO")),
                str(value.get("framework", "TODO")),
                tuple(value.get("serving_stacks", [])),
            )
            for key, value in data.items()
            if not key.startswith("_")
        }

    def _load_profiles(self) -> dict[str, Profile]:
        found: dict[str, Profile] = {}
        for path in sorted((self.root / "profiles").glob("*.json")):
            data = _load_json(path)
            try:
                profile = Profile(
                    name=data["name"],
                    title=data["title"],
                    description=data["description"],
                    agents=tuple(data["agents"]),
                    agents_if_database=tuple(data.get("agents_if_database", [])),
                    rules=tuple(data["rules"]),
                    workflows=tuple(data["workflows"]),
                    technologies=tuple(data["technologies"]),
                    stacks=tuple(data.get("stacks", [])),
                    template=data.get("template", "base"),
                    structure=tuple(data.get("structure", [])),
                )
            except KeyError as exc:
                raise KitError(f"Profile {path.name} is missing field {exc}") from None
            found[profile.name] = profile
        rank = {name: i for i, name in enumerate(PROFILE_ORDER)}
        return dict(sorted(found.items(), key=lambda kv: (rank.get(kv[0], 50), kv[0])))

    # Content available on disk -------------------------------------------------------
    def available_agents(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "agents").glob("*.md"))

    def available_stacks(self) -> list[str]:
        return sorted(p.parent.name for p in (self.root / "stacks").glob("*/README.md"))

    def agent_title(self, agent: str) -> str:
        """Human title from the agent's first heading: ``# 02 - Backend Agent``."""
        path = self.root / "agents" / f"{agent}.md"
        try:
            first = path.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, IndexError):
            return agent
        return first.lstrip("# ").strip() or agent

    # Resolution ------------------------------------------------------------------------
    def resolve(self, selection: Selection) -> Resolved:
        profile = self._require(self.profiles, selection.profile, "profile")
        if selection.technology not in profile.technologies:
            raise KitError(
                f"Technology '{selection.technology}' is not offered by profile "
                f"'{profile.name}'. Choose one of: {', '.join(profile.technologies)}",
                EXIT_USAGE,
            )
        technology = self._require(self.technologies, selection.technology, "technology")
        database = self._require(self.databases, selection.database, "database")
        deployment = self._require(self.deployments, selection.deployment, "deployment")
        for assistant in selection.assistants:
            self._require(self.assistants, assistant, "assistant")

        available_stacks = set(self.available_stacks())
        unknown = [s for s in selection.extra_stacks if s not in available_stacks]
        if unknown:
            raise KitError(
                f"Unknown stack(s): {', '.join(unknown)}. "
                f"Available: {', '.join(sorted(available_stacks))}",
                EXIT_USAGE,
            )

        agents = list(profile.agents)
        if selection.database != "none":
            agents += list(profile.agents_if_database)
        available_agents = set(self.available_agents())
        missing = [a for a in agents if a not in available_agents]
        if missing:
            raise KitError(f"Profile '{profile.name}' references missing agents: {missing}")
        order = {name: i for i, name in enumerate(sorted(available_agents))}

        deployed = deployment_in_scope(selection.deployment)
        stacks = [
            *technology.stacks,
            *(technology.serving_stacks if deployed else ()),
            *database.stacks,
            *deployment.stacks,
            *profile.stacks,
            *selection.extra_stacks,
        ]
        return Resolved(
            profile=profile,
            agents=tuple(sorted(_unique(agents), key=order.__getitem__)),
            rules=profile.rules,
            workflows=profile.workflows,
            stacks=tuple(s for s in _unique(stacks) if s in available_stacks),
            assistants=_unique(selection.assistants),
            structure=tuple(d for d in profile.structure if deployed or not _is_deploy_dir(d)),
        )

    @staticmethod
    def _require(options: dict, key: str, kind: str):
        if key not in options:
            raise KitError(
                f"Unknown {kind} '{key}'. Choose one of: {', '.join(options)}", EXIT_USAGE
            )
        return options[key]
