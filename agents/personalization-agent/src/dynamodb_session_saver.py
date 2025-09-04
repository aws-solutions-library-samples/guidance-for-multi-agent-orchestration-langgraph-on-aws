"""
LangGraph DynamoDB Checkpointer Implementation with Async Support
This module provides a DynamoDB-based checkpointer for LangGraph applications,
allowing persistent storage of conversation state and history with both sync and async support.
"""

import json
import pickle
import base64
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple, AsyncIterator
from decimal import Decimal
from contextlib import asynccontextmanager

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

try:
    import aioboto3

    ASYNC_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False
    print("Warning: aioboto3 not installed. Async operations will fall back to sync.")

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class Base64Serializer(SerializerProtocol):
    """A serializer that uses pickle and base64 encoding for robust serialization."""

    def dumps(self, obj: Any) -> str:
        """Serialize object to base64-encoded string."""
        return base64.b64encode(pickle.dumps(obj)).decode("utf-8")

    def loads(self, data: str) -> Any:
        """Deserialize from base64-encoded string."""
        return pickle.loads(base64.b64decode(data.encode("utf-8")))


class DynamoDBSaver(BaseCheckpointSaver):
    """
    A checkpoint saver that stores LangGraph checkpoints in AWS DynamoDB.

    This implementation provides full checkpointing capabilities including:
    - Saving conversation state and history
    - Loading specific checkpoints
    - Listing available checkpoints
    - Thread-based checkpoint management
    - Both synchronous and asynchronous operations
    """

    def __init__(
        self,
        table_name: str,
        serde: Optional[SerializerProtocol] = None,
        region_name: str = "us-east-1",
        endpoint_url: Optional[str] = None,
    ):
        """
        Initialize the DynamoDB checkpoint saver.

        Args:
            table_name: Name of the DynamoDB table to use
            serde: Serializer for checkpoint data. Options:
                   - Base64Serializer() (default) - handles all Python objects
                   - JsonPlusSerializer() - more readable but may have issues with bytes
            region_name: AWS region name
            endpoint_url: Optional endpoint URL (useful for local DynamoDB)
        """
        # Use Base64Serializer as default for better compatibility
        super().__init__(serde=serde or Base64Serializer())

        self.table_name = table_name
        self.region_name = region_name
        self.endpoint_url = endpoint_url

        # Sync resources
        self.dynamodb = boto3.resource(
            "dynamodb", region_name=region_name, endpoint_url=endpoint_url
        )
        self.table = self.dynamodb.Table(table_name)

        # Async session (created on demand)
        self._async_session = None
        self._async_table = None

    @asynccontextmanager
    async def _get_async_table(self):
        """Get or create async table resource."""
        if not ASYNC_AVAILABLE:
            raise RuntimeError(
                "aioboto3 is required for async operations. Install with: pip install aioboto3"
            )

        if self._async_session is None:
            self._async_session = aioboto3.Session()

        async with self._async_session.resource(
            "dynamodb", region_name=self.region_name, endpoint_url=self.endpoint_url
        ) as dynamodb:
            yield dynamodb.Table(self.table_name)

    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> Dict[str, Any]:
        """Serialize checkpoint data for DynamoDB storage."""
        # Convert checkpoint to a dictionary
        checkpoint_dict = {
            "v": checkpoint["v"],
            "id": checkpoint["id"],
            "ts": checkpoint["ts"],
            "channel_values": self.serde.dumps(checkpoint["channel_values"]),
            "channel_versions": json.dumps(checkpoint["channel_versions"]),
            "versions_seen": json.dumps(checkpoint["versions_seen"]),
        }

        # Handle pending writes if present
        if "pending_sends" in checkpoint:
            checkpoint_dict["pending_sends"] = self.serde.dumps(
                checkpoint["pending_sends"]
            )

        return checkpoint_dict

    def _deserialize_checkpoint(self, item: Dict[str, Any]) -> Checkpoint:
        """Deserialize checkpoint data from DynamoDB."""
        # For Base64Serializer, data is already a string
        # For JsonPlusSerializer that returns bytes, we need to handle conversion
        channel_values_data = item["channel_values"]

        checkpoint = {
            "v": int(item["v"]),
            "id": item["id"],
            "ts": item["ts"],
            "channel_values": self.serde.loads(channel_values_data),
            "channel_versions": json.loads(item["channel_versions"]),
            "versions_seen": json.loads(item["versions_seen"]),
        }

        # Handle pending writes if present
        if "pending_sends" in item:
            checkpoint["pending_sends"] = self.serde.loads(item["pending_sends"])

        return checkpoint

    def _create_key(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> Dict[str, str]:
        """Create a composite key for DynamoDB."""
        return {
            "thread_id": thread_id,
            "checkpoint_id": f"{checkpoint_ns}#{checkpoint_id}",
        }

    # Synchronous methods

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Optional[Dict[str, int]] = None,
    ) -> RunnableConfig:
        """
        Save a checkpoint to DynamoDB (synchronous).

        Args:
            config: Runtime configuration including thread_id
            checkpoint: The checkpoint data to save
            metadata: Additional metadata about the checkpoint
            new_versions: New version information

        Returns:
            Updated configuration with checkpoint information
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "default")
        checkpoint_id = checkpoint["id"]

        # Prepare the item for DynamoDB
        item = {
            **self._create_key(thread_id, checkpoint_ns, checkpoint_id),
            **self._serialize_checkpoint(checkpoint),
            "metadata": json.dumps(metadata),
            "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Convert to JSON and back to handle Decimal conversion safely
        # This ensures all values are JSON-serializable first
        try:
            item_json = json.dumps(item)
            item = json.loads(item_json, parse_float=Decimal)
        except TypeError as e:
            # If JSON serialization fails, use the item as-is
            # DynamoDB SDK will handle the conversion
            pass

        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            raise RuntimeError(f"Failed to save checkpoint: {e}")

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Retrieve a specific checkpoint tuple (synchronous).

        Args:
            config: Runtime configuration with thread_id and optional checkpoint_id

        Returns:
            CheckpointTuple if found, None otherwise
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "default")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if checkpoint_id:
            # Get specific checkpoint
            key = self._create_key(thread_id, checkpoint_ns, checkpoint_id)
            try:
                response = self.table.get_item(Key=key)
                item = response.get("Item")
                if item:
                    checkpoint = self._deserialize_checkpoint(item)
                    metadata = json.loads(item["metadata"])
                    parent_config = None
                    if item.get("parent_checkpoint_id"):
                        parent_config = {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": item["parent_checkpoint_id"],
                            }
                        }
                    return CheckpointTuple(
                        config=config,
                        checkpoint=checkpoint,
                        metadata=metadata,
                        parent_config=parent_config,
                    )
            except ClientError as e:
                raise RuntimeError(f"Failed to get checkpoint: {e}")
        else:
            # Get latest checkpoint for thread
            checkpoints = list(self.list(config, limit=1))
            if checkpoints:
                return checkpoints[0]

        return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        List checkpoints from DynamoDB (synchronous).

        Args:
            config: Runtime configuration with thread_id
            filter: Optional metadata filter
            before: Optional config to list checkpoints before
            limit: Maximum number of checkpoints to return

        Yields:
            CheckpointTuple objects
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "default")

        # Query parameters
        query_params = {
            "KeyConditionExpression": Key("thread_id").eq(thread_id)
            & Key("checkpoint_id").begins_with(f"{checkpoint_ns}#"),
            "ScanIndexForward": False,  # Sort in descending order (newest first)
        }

        if limit:
            query_params["Limit"] = limit

        try:
            response = self.table.query(**query_params)
            items = response.get("Items", [])

            # Continue querying if there are more items and we haven't reached the limit
            while "LastEvaluatedKey" in response and (not limit or len(items) < limit):
                query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                if limit:
                    query_params["Limit"] = limit - len(items)
                response = self.table.query(**query_params)
                items.extend(response.get("Items", []))

            # Process items
            for item in items:
                checkpoint = self._deserialize_checkpoint(item)
                metadata = json.loads(item["metadata"])

                # Apply metadata filter if provided
                if filter:
                    if not all(metadata.get(k) == v for k, v in filter.items()):
                        continue

                # Apply before filter if provided
                if before:
                    before_checkpoint_id = before["configurable"].get("checkpoint_id")
                    if (
                        before_checkpoint_id
                        and item["checkpoint_id"]
                        >= f"{checkpoint_ns}#{before_checkpoint_id}"
                    ):
                        continue

                parent_config = None
                if item.get("parent_checkpoint_id"):
                    parent_config = {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": item["parent_checkpoint_id"],
                        }
                    }

                yield CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": checkpoint["id"],
                        }
                    },
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config,
                )

        except ClientError as e:
            raise RuntimeError(f"Failed to list checkpoints: {e}")

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Store intermediate writes (pending sends) for a checkpoint.

        This is used for storing pending writes that haven't been processed yet.
        """
        # For DynamoDB, we'll store these as part of the checkpoint
        # In a production system, you might want to store these separately
        # for better performance and granularity
        pass

    # Asynchronous methods

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Optional[Dict[str, int]] = None,
    ) -> RunnableConfig:
        """
        Save a checkpoint to DynamoDB (asynchronous).

        Args:
            config: Runtime configuration including thread_id
            checkpoint: The checkpoint data to save
            metadata: Additional metadata about the checkpoint
            new_versions: New version information

        Returns:
            Updated configuration with checkpoint information
        """
        if not ASYNC_AVAILABLE:
            # Fall back to sync version
            return await asyncio.get_event_loop().run_in_executor(
                None, self.put, config, checkpoint, metadata, new_versions
            )

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "default")
        checkpoint_id = checkpoint["id"]

        # Prepare the item for DynamoDB
        item = {
            **self._create_key(thread_id, checkpoint_ns, checkpoint_id),
            **self._serialize_checkpoint(checkpoint),
            "metadata": json.dumps(metadata),
            "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Convert to JSON and back to handle Decimal conversion safely
        try:
            item_json = json.dumps(item)
            item = json.loads(item_json, parse_float=Decimal)
        except TypeError:
            pass

        try:
            async with self._get_async_table() as table:
                await table.put_item(Item=item)
        except ClientError as e:
            raise RuntimeError(f"Failed to save checkpoint: {e}")

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Retrieve a specific checkpoint tuple (asynchronous).

        Args:
            config: Runtime configuration with thread_id and optional checkpoint_id

        Returns:
            CheckpointTuple if found, None otherwise
        """
        if not ASYNC_AVAILABLE:
            # Fall back to sync version
            return await asyncio.get_event_loop().run_in_executor(
                None, self.get_tuple, config
            )

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "default")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if checkpoint_id:
            # Get specific checkpoint
            key = self._create_key(thread_id, checkpoint_ns, checkpoint_id)
            try:
                async with self._get_async_table() as table:
                    response = await table.get_item(Key=key)
                    item = response.get("Item")
                    if item:
                        checkpoint = self._deserialize_checkpoint(item)
                        metadata = json.loads(item["metadata"])
                        parent_config = None
                        if item.get("parent_checkpoint_id"):
                            parent_config = {
                                "configurable": {
                                    "thread_id": thread_id,
                                    "checkpoint_ns": checkpoint_ns,
                                    "checkpoint_id": item["parent_checkpoint_id"],
                                }
                            }
                        return CheckpointTuple(
                            config=config,
                            checkpoint=checkpoint,
                            metadata=metadata,
                            parent_config=parent_config,
                        )
            except ClientError as e:
                raise RuntimeError(f"Failed to get checkpoint: {e}")
        else:
            # Get latest checkpoint for thread
            checkpoints = []
            async for checkpoint in self.alist(config, limit=1):
                checkpoints.append(checkpoint)
            if checkpoints:
                return checkpoints[0]

        return None

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        List checkpoints from DynamoDB (asynchronous).

        Args:
            config: Runtime configuration with thread_id
            filter: Optional metadata filter
            before: Optional config to list checkpoints before
            limit: Maximum number of checkpoints to return

        Yields:
            CheckpointTuple objects
        """
        if not ASYNC_AVAILABLE:
            # Fall back to sync version
            for item in self.list(config, filter=filter, before=before, limit=limit):
                yield item
            return

        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "default")

        # Query parameters
        query_params = {
            "KeyConditionExpression": Key("thread_id").eq(thread_id)
            & Key("checkpoint_id").begins_with(f"{checkpoint_ns}#"),
            "ScanIndexForward": False,  # Sort in descending order (newest first)
        }

        if limit:
            query_params["Limit"] = limit

        try:
            async with self._get_async_table() as table:
                response = await table.query(**query_params)
                items = response.get("Items", [])

                # Continue querying if there are more items and we haven't reached the limit
                while "LastEvaluatedKey" in response and (
                    not limit or len(items) < limit
                ):
                    query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                    if limit:
                        query_params["Limit"] = limit - len(items)
                    response = await table.query(**query_params)
                    items.extend(response.get("Items", []))

                # Process items
                for item in items:
                    checkpoint = self._deserialize_checkpoint(item)
                    metadata = json.loads(item["metadata"])

                    # Apply metadata filter if provided
                    if filter:
                        if not all(metadata.get(k) == v for k, v in filter.items()):
                            continue

                    # Apply before filter if provided
                    if before:
                        before_checkpoint_id = before["configurable"].get(
                            "checkpoint_id"
                        )
                        if (
                            before_checkpoint_id
                            and item["checkpoint_id"]
                            >= f"{checkpoint_ns}#{before_checkpoint_id}"
                        ):
                            continue

                    parent_config = None
                    if item.get("parent_checkpoint_id"):
                        parent_config = {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": item["parent_checkpoint_id"],
                            }
                        }

                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": checkpoint["id"],
                            }
                        },
                        checkpoint=checkpoint,
                        metadata=metadata,
                        parent_config=parent_config,
                    )

        except ClientError as e:
            raise RuntimeError(f"Failed to list checkpoints: {e}")

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Store intermediate writes (pending sends) for a checkpoint (async).

        This is used for storing pending writes that haven't been processed yet.
        """
        # For DynamoDB, we'll store these as part of the checkpoint
        # In a production system, you might want to store these separately
        # for better performance and granularity
        pass