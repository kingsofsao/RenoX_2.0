"""Verify the FalkorDB Cloud connection for ResearchMind AI.

Connects to the `researchmind_connection_test` graph (kept separate so the sample
nodes never pollute the real `researchmind` knowledge graph), upserts a small sample of
Paper -> Method -> Limitation data, and prints it back.
Safe to rerun: all writes use MERGE on unique ids, so no duplicates are created.
"""

import sys
import os

from dotenv import load_dotenv
from falkordb import FalkorDB
from redis.exceptions import AuthenticationError, ConnectionError, ResponseError, TimeoutError

GRAPH_NAME = "researchmind_connection_test"

# Each label is keyed on `id`; MERGE matches on it so reruns update instead of duplicating.
SEED_QUERY = """
MERGE (p:Paper {id: $paper_id})
  SET p.title = $paper_title, p.year = $paper_year
MERGE (m:Method {id: $method_id})
  SET m.name = $method_name
MERGE (l:Limitation {id: $limitation_id})
  SET l.description = $limitation_description
MERGE (p)-[:USES_METHOD]->(m)
MERGE (p)-[:HAS_LIMITATION]->(l)
MERGE (m)-[:HAS_LIMITATION]->(l)
"""

SAMPLE = {
    "paper_id": "paper-attention-2017",
    "paper_title": "Attention Is All You Need",
    "paper_year": 2017,
    "method_id": "method-transformer",
    "method_name": "Transformer (self-attention)",
    "limitation_id": "limitation-quadratic-attention",
    "limitation_description": "Self-attention cost grows quadratically with sequence length",
}

READ_QUERY = """
MATCH (p:Paper)-[:USES_METHOD]->(m:Method),
      (p)-[:HAS_LIMITATION]->(l:Limitation)
RETURN p.title, m.name, l.description
ORDER BY p.title
"""

COUNT_QUERY = """
MATCH (n) WHERE n:Paper OR n:Method OR n:Limitation
RETURN labels(n)[0] AS label, count(n) AS total
ORDER BY label
"""


def ensure_indexes(graph):
    """Create range indexes on `id` so MERGE lookups stay fast. Ignores 'already exists'."""
    for label in ("Paper", "Method", "Limitation"):
        try:
            graph.create_node_range_index(label, "id")
        except ResponseError as e:
            if "already indexed" not in str(e).lower():
                raise


def main() -> int:
    load_dotenv()
    url = os.getenv("FALKORDB_URL")
    if not url:
        print("ERROR: FALKORDB_URL is not set. Add it to your .env file (see .env.example).")
        return 1

    db = None
    try:
        print("Connecting to FalkorDB...")
        db = FalkorDB.from_url(url)
        graph = db.select_graph(GRAPH_NAME)

        # Cheap round-trip to confirm the connection and credentials actually work.
        graph.query("RETURN 1")
        print(f"Connected. Using graph '{GRAPH_NAME}'.")

        ensure_indexes(graph)

        seed = graph.query(SEED_QUERY, SAMPLE)
        print(f"Seed complete: {seed.nodes_created} nodes created, "
              f"{seed.relationships_created} relationships created "
              f"(0 and 0 on reruns means idempotency works).")

        print("\nPaper -> Method -> Limitation:")
        rows = graph.ro_query(READ_QUERY).result_set
        if not rows:
            print("  (no results - seed data missing?)")
            return 1
        for title, method, limitation in rows:
            print(f"  Paper:      {title}")
            print(f"  Method:     {method}")
            print(f"  Limitation: {limitation}")

        print("\nNode counts:")
        for label, total in graph.ro_query(COUNT_QUERY).result_set:
            print(f"  {label}: {total}")

        print("\nSUCCESS: FalkorDB connection verified.")
        return 0

    except AuthenticationError:
        print("ERROR: Authentication failed. Check the username/password in FALKORDB_URL.")
    except (ConnectionError, TimeoutError) as e:
        print(f"ERROR: Could not reach FalkorDB. Check host/port in FALKORDB_URL and your network.\n  {e}")
    except ResponseError as e:
        print(f"ERROR: FalkorDB rejected a query: {e}")
    except ValueError as e:
        print(f"ERROR: FALKORDB_URL looks malformed: {e}")
    finally:
        if db is not None:
            try:
                db.close()
                print("Connection closed.")
            except Exception:
                pass
    return 1


if __name__ == "__main__":
    sys.exit(main())
