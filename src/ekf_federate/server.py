from functools import cache
import traceback
import requests
import logging
import socket
import json
import os

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from oedisi.componentframework.system_configuration import ComponentStruct
from oedisi.types.common import ServerReply, HeathCheck, DefaultFileNames
from oedisi.types.common import BrokerConfig

app = FastAPI()


@cache
def kubernetes_service():
    if "KUBERNETES_SERVICE_NAME" in os.environ:
        # works with kurenetes
        return os.environ["KUBERNETES_SERVICE_NAME"]
    elif "SERVICE_NAME" in os.environ:
        return os.environ["SERVICE_NAME"]  # works with minikube
    else:
        return None


def build_url(host: str, port: int, enpoint: list):

    if kubernetes_service():
        logging.info("Containers running in docker-compose environment")
        url = f"http://{host}.{kubernetes_service()}:{port}/"
    else:
        logging.info("Containers running in kubernetes environment")
        url = f"http://{host}:{port}/"
    url = url + "/".join(enpoint)
    logging.info(f"Built url {url}")
    return url


@app.get("/")
async def read_root():
    hostname = socket.gethostname()
    host_ip = socket.gethostbyname(hostname)
    response = HeathCheck(
        hostname=hostname,
        host_ip=host_ip
    ).dict()
    return JSONResponse(response, 200)
def run_simulator(broker_config: BrokerConfig) -> None:
    import subprocess
    import helics
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    binary_path = os.path.join(current_dir, "bin", "state-estimator-gadal")
    if not os.path.exists(binary_path):
        sibling_path = os.path.join(current_dir, "..", "..", "bin", "state-estimator-gadal")
        if os.path.exists(sibling_path):
            binary_path = sibling_path
        else:
            binary_path = "./bin/state-estimator-gadal"
            
    logging.info(f"Starting simulator binary from: {binary_path}")
    env = os.environ.copy()
    env["HELICS_BROKER"] = f"{broker_config.broker_ip}:{broker_config.broker_port}"
    
    # Configure dynamic linker search paths to locate libhelics and libzmq
    helics_lib = os.path.join(os.path.dirname(helics.__file__), "install", "lib")
    helics_lib64 = os.path.join(os.path.dirname(helics.__file__), "install", "lib64")
    env["LD_LIBRARY_PATH"] = f"{helics_lib}:{helics_lib64}:" + env.get("LD_LIBRARY_PATH", "")
    
    try:
        subprocess.run([binary_path], env=env, check=True)
        logging.info("Simulator binary completed successfully.")
    except Exception as e:
        logging.exception("Error running simulator binary:")
        raise


@app.post("/run")
async def run_model(broker_config: BrokerConfig, background_tasks: BackgroundTasks):
    logging.info(broker_config)
    feeder_host = broker_config.feeder_host
    feeder_port = broker_config.feeder_port
    url = build_url(feeder_host, feeder_port, ['sensor'])
    logging.info(f"Making a request to url - {url}")
    try:
        reply = requests.get(url)
        sensor_data = reply.json()
        if not sensor_data:
            msg = "empty sensor list"
            raise HTTPException(404, msg)
        logging.info(f"Received sensor data {sensor_data}")
        logging.info("Writing sensor data to sensors.json")
        with open("sensors.json", "w") as outfile:
            json.dump(sensor_data, outfile)

        background_tasks.add_task(run_simulator, broker_config)
        response = ServerReply(
            detail=f"Task sucessfully added."
        ).dict()
        return JSONResponse(response, 200)
    except Exception as e:
        err = traceback.format_exc()
        raise HTTPException(500, str(err))


@app.post("/configure")
async def configure(component_struct: ComponentStruct):
    component = component_struct.component
    params = component.parameters
    params["name"] = component.name
    links = {}
    for link in component_struct.links:
        links[link.target_port] = f"{link.source}/{link.source_port}"
    json.dump(links, open(DefaultFileNames.INPUT_MAPPING.value, "w"))
    json.dump(params, open(DefaultFileNames.STATIC_INPUTS.value, "w"))
    response = ServerReply(
        detail=f"Sucessfully updated configuration files."
    ).dict()
    return JSONResponse(response, 200)

def run_sim_cli():
    import helics
    import subprocess
    import sys
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    binary_path = os.path.join(current_dir, "bin", "state-estimator-gadal")
    if not os.path.exists(binary_path):
        sibling_path = os.path.join(current_dir, "..", "..", "bin", "state-estimator-gadal")
        if os.path.exists(sibling_path):
            binary_path = sibling_path
        else:
            binary_path = "./bin/state-estimator-gadal"
            
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Starting simulator binary from: {binary_path}")
    env = os.environ.copy()
    
    # Configure dynamic linker search paths to locate libhelics and libzmq
    helics_lib = os.path.join(os.path.dirname(helics.__file__), "install", "lib")
    helics_lib64 = os.path.join(os.path.dirname(helics.__file__), "install", "lib64")
    env["LD_LIBRARY_PATH"] = f"{helics_lib}:{helics_lib64}:" + env.get("LD_LIBRARY_PATH", "")
    
    try:
        subprocess.run([binary_path], env=env, check=True)
        logging.info("Simulator binary completed successfully.")
    except Exception as e:
        logging.exception("Error running simulator binary:")
        sys.exit(1)

def main():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get('PORT', '5903')))

if __name__ == "__main__":
    main()
