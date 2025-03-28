import json
import networkx as nx
import asyncio
import aiohttp
import pandas as pd
import matplotlib.pyplot as plt
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

# FastAPI app
app = FastAPI()

# Thread pool for parallel execution
executor = ThreadPoolExecutor(max_workers=3)

# Function to simulate checking health (async version for non-blocking)
async def check_health(component_id, status):
    await asyncio.sleep(1)  
    return {"id": component_id, "health": status}

# Function to create the DAG from the JSON data
def create_dag(data: Dict) -> nx.DiGraph:
    G = nx.DiGraph()
    for subsystem in data['system']['subsystems']:
        for component in subsystem['components']:
            node = component['id']
            for dependency in component['dependencies']:
                G.add_edge(node, dependency)
    return G

# Function to perform BFS traversal on the DAG and check health of nodes
async def bfs_health_check(G: nx.DiGraph, data: Dict):
    visited = set()
    bfs_order = []
    health_results = {}

    # Start BFS from all nodes to ensure no node is missed
    for start_node in G.nodes():
        if start_node not in visited:
            queue = [start_node]
            visited.add(start_node)

            while queue:
                node = queue.pop(0)
                bfs_order.append(node)

                # Find the component related to the node
                component = next((comp for sub in data['system']['subsystems'] for comp in sub['components'] if comp['id'] == node), None)
                if component:
                    # Simulate health check with async task
                    health = await check_health(node, component['status'])
                    health_results[health['id']] = {
                        'id': health['id'],
                        'health': health['health'],
                        'type': component['type'],
                        'status': component['status'],
                        'cpu_usage': component.get('cpu_usage', 'N/A'),
                        'memory_usage': component.get('memory_usage', 'N/A'),
                        'disk_usage': component.get('disk_usage', 'N/A'),
                    }

                # Add unvisited neighbors to the queue
                for neighbor in G.neighbors(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

    return bfs_order, health_results

# Function to generate and save graph image locally
def generate_graph_image(G: nx.DiGraph):
    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_size=3000, node_color='lightblue', font_size=10, font_weight='bold')
    plt.title('System Dependency Graph')

    img_path = "graph.png"
    plt.savefig(img_path, format='PNG')
    plt.close()
    return img_path

# Endpoint to accept a JSON file upload
@app.post("/upload-json/")
async def upload_json(file: UploadFile = File(...)):
    contents = await file.read()
    
    try:
        data = json.loads(contents)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    G = create_dag(data)

    # Perform BFS and health check
    bfs_order, health_results = await bfs_health_check(G, data)

    # Create the data table for the response
    table_data = [{
        'ID': result['id'],
        'Type': result['type'],
        'Status': result['status'],
        'CPU': result['cpu_usage'],
        'Memory': result['memory_usage'],
        'Disk': result['disk_usage'],
    } for result in health_results.values()]

    df = pd.DataFrame(table_data)
    health_table_str = df.to_string(index=False)

    img_path = generate_graph_image(G)

    response = f"""
    System Health Report:
    {health_table_str}

    BFS Traversal Order: {', '.join(bfs_order)}

    Graph Image: {os.path.abspath(img_path)}
    """
    return PlainTextResponse(content=response)

# Endpoint to serve the saved graph image
@app.get("/graph-image/") 
async def get_graph_image():
    img_path = "graph.png"
    
    if os.path.exists(img_path):
        return FileResponse(img_path)
    else:
        raise HTTPException(status_code=404, detail="Graph image not found. Please upload a JSON file first.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
