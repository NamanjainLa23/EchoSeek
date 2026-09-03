import os
import boto3
import json
import yaml
from dotenv import load_dotenv

class AnthropicModel:
    def __init__(self):
        self.cfg = self.get_config()
        self.client = None
    
    def get_config(self):
        load_dotenv()

        with open("server/config.yaml", "r") as fp:
            cfg = yaml.safe_load(fp)
        aws_region = os.getenv("AWS_REGION")
        if aws_region:
            cfg["aws_region"] = aws_region
        aws_profile = os.getenv("AWS_PROFILE_NAME")
        if aws_profile:
            cfg["aws_profile"] = aws_profile

        return cfg

    def create_bedrock_client(self):
        try:
            session = boto3.Session()
            self.client = session.client("bedrock-runtime", region_name=self.cfg['aws_region'])
        except Exception as e:
            print(f"Failed to create bedrock client: {e}")

    def build_payload(self, sys_prompt=None, prompt=None, role="user"):
        payload = {}
        messages = []                         
        payload["anthropic_version"] =self.cfg['anthropic_version']
        if sys_prompt:
            payload["system"] = sys_prompt
        messages.append({"role": role, "content": prompt})
        payload["max_tokens"] = self.cfg['max_tokens']
        payload["temperature"] = self.cfg['temperature']
        payload["messages"] = messages
        return payload

    def call_model(self, prompt=None, sys_prompt=None, role="user"):
        """
        Calls the Anthropic model with the provided prompt.
        If sys_prompt is given, it sets the system context.
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        payload = self.build_payload(sys_prompt, prompt, role)
        response = self.client.invoke_model(
            modelId=self.cfg['id'],
            contentType=self.cfg['content_type'],
            accept=self.cfg['accept'],
            body=json.dumps(payload)
        )
        result = json.loads(response["body"].read())
        return result

class TitanModel:
    def __init__(self):
        self.cfg = self.get_config()
        self.client = None
    
    def get_config(self):
        load_dotenv()

        with open("server/config.yaml", "r") as fp:
            cfg = yaml.safe_load(fp)
        aws_region = os.getenv("AWS_REGION")
        if aws_region:
            cfg["aws_region"] = aws_region
        aws_profile = os.getenv("AWS_PROFILE_NAME")
        if aws_profile:
            cfg["aws_profile"] = aws_profile

        return cfg
    
    def create_bedrock_client(self):
        try:
            session = boto3.Session()
            self.client = session.client("bedrock-runtime", region_name=self.cfg['aws_region'])
        except Exception as e:
            print(f"Failed to create bedrock client: {e}")

    def call_model(self, text, role="user"):
        response = self.client.invoke_model(
            modelId = "amazon.titan-embed-text-v2:0",
            contentType = self.cfg['content_type'],
            accept = self.cfg['accept'],
            body = json.dumps({"inputText":text})
        )
        result = json.loads(response["body"].read())
        # print(result)
        return result

