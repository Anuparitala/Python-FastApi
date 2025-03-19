import json
import networkx as nx
import asyncio
import aiohttp
import pandas as pd
import matplotlib.pyplot as plt
from fastapi import FastAPI, File, UploadFile
from io import BytesIO
from fastapi.responses import PlainTextResponse, FileResponse
import os
from tabulate import tabulate
from concurrent.futures import ThreadPoolExecutor

# FastAPI app
app = FastAPI()

# Thread pool for parallel execution
executor = ThreadPoolExecutor(max_workers=10)

# Function to simulate checking health (now thread-safe)
def check_health(component_id, status):
    import time
    time.sleep(1)  # Simulate network delay
    return {"id": component_id, "health": status}

# Function to create the DAG from the JSON data
def create_dag(data):
    G = nx.DiGraph()
    for subsystem in data['system']['subsystems']:
        for component in subsystem['components']:
            node = component['id']
            for dependency in component['dependencies']:
                G.add_edge(node, dependency)
    return G

# Function to traverse the graph and check health using threading
async def check_health_for_all_nodes(G, data):
    loop = asyncio.get_running_loop()
    health_results = []

    tasks = []
    for node in G.nodes():
        component = None
        for subsystem in data['system']['subsystems']:
            for comp in subsystem['components']:
                if comp['id'] == node:
                    component = comp
                    break
        
        if component:
            # Run health check in thread pool
            tasks.append(loop.run_in_executor(executor, check_health, node, component['status']))
    
    # Wait for all health check tasks to complete
    health_responses = await asyncio.gather(*tasks)

    # Store health results
    for result in health_responses:
        for subsystem in data['system']['subsystems']:
            for component in subsystem['components']:
                if component['id'] == result['id']:
                    component['health'] = result['health']
                    health_results.append(component)
    
    return health_results

# Function to generate and save graph image locally
def generate_graph_image(G):
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
        return PlainTextResponse(status_code=400, content=f"Invalid JSON: {str(e)}")

    G = create_dag(data)

    # Run health checks in parallel using threading
    health_results = await check_health_for_all_nodes(G, data)

    table_data = []
    for result in health_results:
        table_row = {
            'ID': result['id'],
            'Type': result['type'],
            'Status': result['status'],
            'CPU': result.get('cpu_usage', 'N/A'),
            'Memory': result.get('memory_usage', 'N/A'),
            'Disk': result.get('disk_usage', 'N/A'),
        }
        table_data.append(table_row)

    df = pd.DataFrame(table_data)
    table = df.values.tolist()
    headers = df.columns.tolist()
    health_table_str = tabulate(table, headers=headers, tablefmt="grid")

    img_path = generate_graph_image(G)

    response = f"""
System Health Report:

{health_table_str}

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
        return PlainTextResponse(status_code=404, content="Graph image not found. Please upload a JSON file before accessing the Graph Image.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)
