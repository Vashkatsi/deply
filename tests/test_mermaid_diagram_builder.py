import unittest

from deply.diagrams.marmaid_diagram_builder import MermaidDiagramBuilder


class TestMermaidDiagramBuilder(unittest.TestCase):
    def test_build_diagram(self):
        builder = MermaidDiagramBuilder()
        # Add some edges
        builder.add_edge("A", "B", False)  # Initially no violation
        builder.add_edge("B", "C", True)  # Violation
        builder.add_edge("A", "C", False)  # No violation
        # Update edge "A" -> "B" with a violation flag True
        builder.add_edge("A", "B", True)

        diagram = builder.build_diagram()
        # Check that diagram starts with a mermaid code block and flowchart declaration
        self.assertTrue(diagram.startswith("```mermaid"), "Diagram should start with ```mermaid")
        self.assertIn("flowchart LR", diagram, "Diagram should include 'flowchart LR'")
        # Check that all layers appear (sorted alphabetically: A, B, C)
        self.assertIn("    A", diagram, "Layer A should be present")
        self.assertIn("    B", diagram, "Layer B should be present")
        self.assertIn("    C", diagram, "Layer C should be present")
        # Check that edges appear
        self.assertIn("    A --> B", diagram, "Edge 'A --> B' should be present")
        self.assertIn("    A --> C", diagram, "Edge 'A --> C' should be present")
        self.assertIn("    B --> C", diagram, "Edge 'B --> C' should be present")
        # Check that violated edges are marked red via linkStyle.
        # According to sorting, the edges should be in order: ("A", "B"), ("A", "C"), ("B", "C")
        # Edge ("A", "B") has been updated to have a violation, so index 0 should be red.
        self.assertIn("linkStyle 0 stroke:red,stroke-width:2px;", diagram, "Edge 0 should have red linkStyle")
        # Edge ("B", "C") is violated and should be at index 2.
        self.assertIn("linkStyle 2 stroke:red,stroke-width:2px;", diagram, "Edge 2 should have red linkStyle")
        # Edge ("A", "C") is not violated; there should be no linkStyle for its index (index 1).
        self.assertNotIn("linkStyle 1 stroke:red,stroke-width:2px;", diagram, "Edge 1 should not have red linkStyle")
        # Check that the diagram ends with the closing code block delimiter
        self.assertTrue(diagram.endswith("```"), "Diagram should end with ```")


if __name__ == "__main__":
    unittest.main()
