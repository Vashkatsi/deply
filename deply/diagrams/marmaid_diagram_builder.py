from typing import Dict, Tuple


class MermaidDiagramBuilder:
    def __init__(self):
        self._edges_with_violation: Dict[Tuple[str, str], bool] = {}

    def add_edge(self, source_layer: str, target_layer: str, has_violation: bool) -> None:
        """
        Adds or updates an edge (source_layer -> target_layer) with a flag indicating
        if a violation occurred. If we’ve already recorded a violation for this edge,
        we keep it as True.
        """
        current_violation = self._edges_with_violation.get((source_layer, target_layer), False)
        self._edges_with_violation[(source_layer, target_layer)] = current_violation or has_violation

    def build_diagram(self) -> str:
        """
        Builds and returns a Mermaid flowchart (as a Markdown code block) that
        shows all layers. Arrows are colored red (via linkStyle) if has_violation=True.
        """
        # Gather unique layers
        layer_set = set()
        for (source, target), _ in self._edges_with_violation.items():
            layer_set.add(source)
            layer_set.add(target)

        # Sort edges by source_layer, then target_layer for consistent output
        sorted_edges = sorted(self._edges_with_violation.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        lines = ["```mermaid", "flowchart LR"]

        # Ensure every layer is at least mentioned so it appears in the diagram
        for layer in sorted(layer_set):
            lines.append(f"    {layer}")

        # We'll collect linkStyle lines separately
        link_style_lines = []
        edge_index = 0

        # Build edges
        for (source, target), violated in sorted_edges:
            lines.append(f"    {source} --> {target}")
            if violated:
                # Mark arrow red
                link_style_lines.append(f"    linkStyle {edge_index} stroke:red,stroke-width:2px;")
            edge_index += 1

        lines.extend(link_style_lines)
        lines.append("```")
        return "\n".join(lines)

    @property
    def edges_with_violation(self) -> Dict[Tuple[str, str], bool]:
        return self._edges_with_violation
