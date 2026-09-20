from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.settings import AWS_REGION, BEDROCK_MODEL_ID

logger = logging.getLogger("auditiq.aws.bedrock")


class BedrockService:
    def __init__(self, model_id: str | None = None, region_name: str | None = None) -> None:
        self.model_id = (model_id or BEDROCK_MODEL_ID or "anthropic.claude-3-haiku-20240307-v1:0").strip()
        self.region = region_name or AWS_REGION or "us-east-1"
        self._client = None
        self._is_ready = False

        try:
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
            self._is_ready = True
        except Exception as e:
            logger.info(f"Bedrock runtime client could not be initialized directly: {e}")
            self._is_ready = False

    def is_available(self) -> bool:
        return self._is_ready and self._client is not None

    def invoke_model(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        if not self.is_available():
            raise RuntimeError("Bedrock runtime client is not available or AWS credentials not configured.")

        # Determine payload based on model family
        if "claude" in self.model_id.lower():
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
            if system_prompt:
                body["system"] = system_prompt
        elif "nova" in self.model_id.lower():
            body = {
                "inferenceConfig": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                },
                "messages": [
                    {"role": "user", "content": [{"text": prompt}]}
                ],
            }
            if system_prompt:
                body["system"] = [{"text": system_prompt}]
        else:
            # Generic/Titan payload
            body = {
                "inputText": f"{system_prompt}\n\n{prompt}" if system_prompt else prompt,
                "textGenerationConfig": {
                    "maxTokenCount": max_tokens,
                    "temperature": temperature,
                },
            }

        try:
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read().decode("utf-8"))

            if "content" in response_body and isinstance(response_body["content"], list):
                # Claude 3 format
                text_parts = [item.get("text", "") for item in response_body["content"] if item.get("type") == "text"]
                return "".join(text_parts).strip()
            elif "output" in response_body and "message" in response_body["output"]:
                # Nova format
                msg = response_body["output"]["message"]
                content = msg.get("content", [])
                return "".join([c.get("text", "") for c in content]).strip()
            elif "results" in response_body:
                # Titan format
                return response_body["results"][0].get("outputText", "").strip()

            return json.dumps(response_body)
        except Exception as e:
            logger.error(f"Bedrock invocation failed for model {self.model_id}: {e}")
            raise


bedrock_service = BedrockService()
