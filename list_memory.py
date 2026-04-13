import argparse
from src.chroma_client import chroma_client

parser = argparse.ArgumentParser(description="List recent memories from ChromaDB")
parser.add_argument("-n", "--number", type=int, default=10, help="Number of recent memories to show (default: 10)")
args = parser.parse_args()

memories = chroma_client.get_all()

for m in memories[-args.number:]:
    print("-" * 50)
    print(m["metadata"]["importance"], m["metadata"]["topics"], m["content"])
