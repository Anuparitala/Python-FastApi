import json
import networkx as nx
import asyncio
import aiohttp
import pandas as pd
import matplotlib.pyplot as plt
from fastapi import FastAPI, File, UploadFile, HTTPException
from io import BytesIO
from fastapi.responses import PlainTextResponse, FileResponse
import os
from tabulate import tabulate

# FastAPI app
app = FastAPI()

# Function to simulate checking health asynchronously
async def check_health(component_id, status):
    # Simulate asynchronous health check (e.g., calling an API)
    await asyncio.sleep(1)  # Simulate network delay
    # Return the actual status of the node (use the input status)
    return {"id": component_id, "health": status}

# Function to create the DAG from the JSON data
def create_dag(data):
    G = nx.DiGraph()

    # Populate the graph with nodes and edges
    for subsystem in data['system']['subsystems']:
        for component in subsystem['components']:
            node = component['id']
            for dependency in component['dependencies']:
                # Add an edge from the component to its dependencies
                G.add_edge(node, dependency)

    return G

# Function to traverse the graph and check health for all nodes (not just BFS)
async def check_health_for_all_nodes(G, data):
    health_results = []
    
    # Iterate through all nodes in the graph (all components)
    for node in G.nodes():
        # Find the component details from the data
        component = None
        for subsystem in data['system']['subsystems']:
            for comp in subsystem['components']:
                if comp['id'] == node:
                    component = comp
                    break
        
        if component:
            # Get health check result for the component (simulate health check here)
            health_status = await check_health(node, component['status'])  # Use the component's actual status
            component['health'] = health_status['health']  # Add health status to component info
            health_results.append(component)

    return health_results

# Function to generate and save graph image locally
def generate_graph_image(G):
    plt.figure(figsize=(8, 6))
    pos = nx.spring_layout(G)  # Layout for better visualization
    nx.draw(G, pos, with_labels=True, node_size=3000, node_color='lightblue', font_size=10, font_weight='bold')
    plt.title('System Dependency Graph')

    # Save the plot to a file
    img_path = "graph.png"
    plt.savefig(img_path, format='PNG')
    plt.close()
    return img_path

# Endpoint to accept a JSON file upload
@app.post("/upload-json/")
async def upload_json(file: UploadFile = File(...), source_node: str = 'LB01'):
    # Read the content of the uploaded file
    contents = await file.read()
    
    try:
        # Parse the JSON content
        data = json.loads(contents)
    except json.JSONDecodeError as e:
        return PlainTextResponse(status_code=400, content=f"Invalid JSON: {str(e)}")

    # Create the DAG from the uploaded data
    G = create_dag(data)

    # Perform health check asynchronously for all nodes (not just BFS traversal)
    health_results = await check_health_for_all_nodes(G, data)

    # Dynamically create the table columns based on the component properties
    # We will include various health-related information like 'id', 'status', 'cpu_usage', 'memory_usage', etc.
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

    # Convert the table data to a DataFrame
    df = pd.DataFrame(table_data)

    # Convert the DataFrame to a list of lists for table formatting
    table = df.values.tolist()

    # Get the column headers
    headers = df.columns.tolist()

    # Create a formatted table using the tabulate library
    health_table_str = tabulate(table, headers=headers, tablefmt="grid")

    # Generate and save the graph image
    img_path = generate_graph_image(G)

    # Create a plain text response with the health table and graph image path
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
        return FileResponse(img_path)  # Return the image file
    else:
        return PlainTextResponse(status_code=404, content="Graph image not found, Please Upload the json file before accessing the Graph Image.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)