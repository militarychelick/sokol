"""Tool Registry Normalization Layer - semantic tool graph."""

from dataclasses import dataclass, field
from typing import Any, Optional, List
from enum import Enum

from sokol.observability.logging import get_logger

logger = get_logger("sokol.runtime.tool_registry")


class RiskLevel(str, Enum):
    """Tool risk level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ToolCapability:
    """Tool capability description."""

    name: str
    description: str
    tags: List[str] = field(default_factory=list)  # e.g., ["filesystem", "read"]
    risk_level: RiskLevel = RiskLevel.MEDIUM
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)


@dataclass
class ToolNode:
    """Tool node in semantic graph."""

    tool_id: str
    capabilities: List[ToolCapability] = field(default_factory=list)
    preferred_contexts: List[str] = field(default_factory=list)  # e.g., ["file_editing", "system_info"]
    dependencies: List[str] = field(default_factory=list)  # Tools that should run first
    conflicts: List[str] = field(default_factory=list)  # Tools that should not co-occur


class ToolRegistry:
    """
    Tool Registry - semantic tool graph.

    This registry:
    - Groups tools by capability tags
    - Provides similarity between tools (lightweight, rule-based)
    - Matches context (intent → capability mapping)
    - Detects conflicts between tools

    This registry DOES NOT:
    - Change execution logic
    - Change tool execution
    - Introduce planner
    - Introduce agent autonomy
    - Change orchestrator flow
    - Change safety logic
    """

    def __init__(self) -> None:
        """Initialize tool registry."""
        self._tool_nodes: dict[str, ToolNode] = {}
        self._capability_index: dict[str, List[str]] = {}  # tag -> tool_ids
        self._context_index: dict[str, List[str]] = {}  # context -> tool_ids

    def register_tool(self, tool_node: ToolNode) -> None:
        """
        Register a tool in the registry.

        Args:
            tool_node: ToolNode to register
        """
        self._tool_nodes[tool_node.tool_id] = tool_node

        # Index by capability tags
        for capability in tool_node.capabilities:
            for tag in capability.tags:
                if tag not in self._capability_index:
                    self._capability_index[tag] = []
                if tool_node.tool_id not in self._capability_index[tag]:
                    self._capability_index[tag].append(tool_node.tool_id)

        # Index by preferred contexts
        for context in tool_node.preferred_contexts:
            if context not in self._context_index:
                self._context_index[context] = []
            if tool_node.tool_id not in self._context_index[context]:
                self._context_index[context].append(tool_node.tool_id)

        logger.debug_data(
            "Tool registered in semantic registry",
            {"tool_id": tool_node.tool_id, "capabilities": len(tool_node.capabilities)},
        )

    def get_tool(self, tool_id: str) -> Optional[ToolNode]:
        """
        Get tool node by ID.

        Args:
            tool_id: Tool ID

        Returns:
            ToolNode if found, None otherwise
        """
        return self._tool_nodes.get(tool_id)

    def get_tools_by_capability(self, tag: str) -> List[str]:
        """
        Get tools by capability tag.

        Args:
            tag: Capability tag (e.g., "filesystem", "read")

        Returns:
            List of tool IDs with this capability
        """
        return self._capability_index.get(tag, [])

    def resolve_candidates(
        self,
        intent: str,
        context: dict,
    ) -> List[str]:
        """
        Resolve candidate tools based on intent and context.

        Args:
            intent: User intent (e.g., "read file")
            context: Context dictionary

        Returns:
            List of candidate tool IDs, sorted by relevance
        """
        candidates = []

        # Lightweight keyword matching (rule-based)
        intent_lower = intent.lower()
        intent_words = set(intent_lower.split())

        for tool_id, tool_node in self._tool_nodes.items():
            score = 0.0

            # Check preferred contexts
            for preferred_context in tool_node.preferred_contexts:
                if preferred_context.lower() in intent_lower:
                    score += 0.3

            # Check capability tags
            for capability in tool_node.capabilities:
                for tag in capability.tags:
                    if tag.lower() in intent_lower:
                        score += 0.2

                    # Check description
                    if capability.description:
                        desc_words = set(capability.description.lower().split())
                        overlap = len(intent_words & desc_words)
                        if overlap > 0:
                            score += 0.1 * overlap

            if score > 0:
                candidates.append((tool_id, score))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        return [tool_id for tool_id, _ in candidates]

    def detect_conflicts(self, tool_id: str) -> List[str]:
        """
        Detect conflicts with other tools.

        Args:
            tool_id: Tool ID to check

        Returns:
            List of conflicting tool IDs
        """
        tool_node = self._tool_nodes.get(tool_id)
        if not tool_node:
            return []

        return tool_node.conflicts

    def get_semantic_neighbors(self, tool_id: str) -> List[str]:
        """
        Get semantically similar tools (related tools graph).

        Args:
            tool_id: Tool ID

        Returns:
            List of similar tool IDs
        """
        tool_node = self._tool_nodes.get(tool_id)
        if not tool_node:
            return []

        neighbors = []

        # Find tools with similar capability tags
        tool_tags = set()
        for capability in tool_node.capabilities:
            tool_tags.update(capability.tags)

        for other_id, other_node in self._tool_nodes.items():
            if other_id == tool_id:
                continue

            other_tags = set()
            for capability in other_node.capabilities:
                other_tags.update(capability.tags)

            # Calculate similarity (Jaccard index)
            intersection = len(tool_tags & other_tags)
            union = len(tool_tags | other_tags)

            if union > 0:
                similarity = intersection / union
                if similarity > 0.3:  # 30% similarity threshold
                    neighbors.append((other_id, similarity))

        # Sort by similarity descending
        neighbors.sort(key=lambda x: x[1], reverse=True)

        return [tool_id for tool_id, _ in neighbors]

    def get_capability_tags(self, tool_id: str) -> List[str]:
        """
        Get all capability tags for a tool.

        Args:
            tool_id: Tool ID

        Returns:
            List of capability tags
        """
        tool_node = self._tool_nodes.get(tool_id)
        if not tool_node:
            return []

        tags = []
        for capability in tool_node.capabilities:
            tags.extend(capability.tags)

        return list(set(tags))

    def get_tool_category(self, tool_id: str) -> str:
        """
        Get tool category based on capabilities.

        Args:
            tool_id: Tool ID

        Returns:
            Tool category (filesystem/network/system/etc.)
        """
        tool_node = self._tool_nodes.get(tool_id)
        if not tool_node:
            return "unknown"

        # Lightweight category inference from tags
        tags = self.get_capability_tags(tool_id)

        if any(tag in tags for tag in ["filesystem", "file", "read", "write", "delete"]):
            return "filesystem"
        elif any(tag in tags for tag in ["network", "http", "request", "api"]):
            return "network"
        elif any(tag in tags for tag in ["system", "info", "process", "memory"]):
            return "system"
        else:
            return "general"

    def get_registry_stats(self) -> dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with registry stats
        """
        return {
            "total_tools": len(self._tool_nodes),
            "total_capabilities": sum(len(node.capabilities) for node in self._tool_nodes.values()),
            "total_tags": len(self._capability_index),
            "total_contexts": len(self._context_index),
        }
