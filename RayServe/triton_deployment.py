import os

import numpy
import requests
from fastapi import FastAPI
from ray import serve
from tritonserver_api import TritonServer

# 1: Define a FastAPI app and wrap it in a deployment with a route handler.
app = FastAPI()


@serve.deployment(route_prefix="/", ray_actor_options={"num_gpus": 1})
@serve.ingress(app)
class TritonDeployment:
    def __init__(self):
        server_options = TritonServer.Options()
        self._triton_server = TritonServer(server_options)
        self._triton_server.start()

        self._models = self._triton_server.model_index()
        for model in self._models:
            print(model)

    @app.get("/test")
    def generate(self, text_input: str, fp16_input: float) -> dict:
        test = self._triton_server.model("test")
        responses = test.infer_async(
            inputs={
                "text_input": numpy.array([text_input], dtype=numpy.object_),
                "fp16_input": numpy.array([[fp16_input]], dtype=numpy.float16),
            }
        )
        for response in responses:
            text_output = response.outputs["text_output"].astype(str)[0]
            fp16_output = response.outputs["fp16_output"].astype(float)[0]

        return {"text_output": text_output, "fp16_output": fp16_output}

    @app.get("/generate")
    def generate(self, text_input: str) -> str:
        trt_llm = self._triton_server.model("ensemble")
        try:
            if not trt_llm.ready():
                return ""
        except:
            return ""

        responses = trt_llm.infer_async(
            inputs={
                "text_input": numpy.array([[text_input]], dtype=numpy.object_),
                "max_tokens": numpy.array([[100]], dtype=numpy.uint32),
                "stop_words": numpy.array([[""]], dtype=numpy.object_),
                "bad_words": numpy.array([[""]], dtype=numpy.object_),
            }
        )
        result = []
        for response in responses:
            result.append(response.outputs["text_output"].astype(str)[0])
        return "".join(result)

    @app.get("/hello")
    def say_hello(self, name: str) -> str:
        return f"Hello {name}!"


# 2: Deploy the deployment.
serve.run(TritonDeployment.bind())

# 3: Query the deployment and print the result.
print(requests.get("http://localhost:8000/hello", params={"name": "Theodore"}).json())
print(
    requests.get(
        "http://localhost:8000/generate", params={"text_input": "Theodore"}
    ).json()
)
print(
    requests.get(
        "http://localhost:8000/test",
        params={"text_input": "Theodore", "fp16_input": 0.5},
    ).json()
)
# "Hello Theodore!"
