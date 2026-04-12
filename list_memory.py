from src.chroma_client import chroma_client

memories = chroma_client.get_all()

for m in memories[-10:]:
    print("-" * 50)
    print(m["metadata"]["importance"], m["metadata"]["topics"], m["content"])
