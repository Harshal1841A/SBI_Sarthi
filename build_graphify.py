import sys, json
from pathlib import Path
from graphify.extract import collect_files, extract
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.report import generate
from graphify.export import to_json
from graphify.detect import save_manifest
from datetime import datetime, timezone

# 1. Structural Extract (parallel=False to fix Windows Pool error)
detect_path = Path('graphify-out/.graphify_detect.json')
if not detect_path.exists():
    from graphify.detect import detect
    d_res = detect(Path('.'))
    detect_path.write_text(json.dumps(d_res, ensure_ascii=False), encoding='utf-8')

detect = json.loads(detect_path.read_text(encoding='utf-8'))
code_files = []
for f in detect.get('files', {}).get('code', []):
    code_files.extend(collect_files(Path(f)) if Path(f).is_dir() else [Path(f)])

if code_files:
    result = extract(code_files, cache_root=Path('.'), parallel=False)
else:
    result = {'nodes':[],'edges':[],'input_tokens':0,'output_tokens':0}

# 2. Merge (mock semantic since no API key)
ast = result
sem = {'nodes':[],'edges':[],'hyperedges':[],'input_tokens':0,'output_tokens':0}

seen = {n['id'] for n in ast['nodes']}
merged_nodes = list(ast['nodes'])
merged_edges = ast['edges']

extraction = {
    'nodes': merged_nodes,
    'edges': merged_edges,
    'hyperedges': [],
    'input_tokens': 0,
    'output_tokens': 0,
}

# 3. Build & Cluster
G = build_from_json(extraction)
communities = cluster(G)
cohesion = score_all(G, communities)
tokens = {'input': 0, 'output': 0}
gods = god_nodes(G)
surprises = surprising_connections(G, communities)

labels = {cid: 'Community ' + str(cid) for cid in communities}
questions = suggest_questions(G, communities, labels)

report = generate(G, communities, cohesion, labels, gods, surprises, detect, tokens, '.', suggested_questions=questions)
Path('graphify-out/GRAPH_REPORT.md').write_text(report, encoding='utf-8')
to_json(G, communities, 'graphify-out/graph.json')

print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(communities)} communities")

analysis = {
    'communities': {str(k): v for k, v in communities.items()},
    'cohesion': {str(k): v for k, v in cohesion.items()},
    'gods': gods,
    'surprises': surprises,
    'questions': questions,
}
Path('graphify-out/.graphify_analysis.json').write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding='utf-8')
Path('graphify-out/.graphify_extract.json').write_text(json.dumps(extraction, indent=2, ensure_ascii=False), encoding='utf-8')

save_manifest(detect.get('all_files') or detect['files'])
