import unittest

from atlas_n8n_graph_safety import connection_count, duplicate_connections


def body_with_edges(*edges):
    connections = {}
    for source, target in edges:
        connections.setdefault(source, {"main": [[]]})["main"][0].append(
            {"node": target, "type": "main", "index": 0}
        )
    return {"connections": connections}


class N8NGraphSafetyTests(unittest.TestCase):
    def test_counts_duplicate_physical_edges(self):
        body = body_with_edges(("A", "B"), ("A", "B"), ("A", "C"))
        self.assertEqual(connection_count(body, "A", "B"), 2)
        self.assertEqual(connection_count(body, "A", "C"), 1)

    def test_reports_only_watched_duplicate_edges(self):
        body = body_with_edges(("A", "B"), ("A", "B"), ("X", "Y"), ("X", "Y"))
        issues = duplicate_connections(body, (("A", "B"), ("M", "N")))
        self.assertEqual(issues, ["duplicate_connection:A->B"])

    def test_malformed_connections_fail_safe_to_zero_count(self):
        self.assertEqual(connection_count({"connections": []}, "A", "B"), 0)
        self.assertEqual(connection_count({}, "A", "B"), 0)


if __name__ == "__main__":
    unittest.main()
