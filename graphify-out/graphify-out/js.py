import json
import csv

with open("graph.json", "r") as f:
    data = json.load(f)

with open("nodes.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Id", "Label"])

    for node in data["nodes"]:
        writer.writerow([
            str(node["id"]).strip(),
            str(node.get("label", node["id"])).strip()
        ])

with open("edges.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Source", "Target", "Type"])

    for edge in data["links"]:
        writer.writerow([
            str(edge["source"]).strip(),
            str(edge["target"]).strip(),
            "Directed"
        ])
