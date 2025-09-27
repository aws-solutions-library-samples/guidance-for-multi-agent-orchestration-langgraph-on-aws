"""
Production WebSocket Event Client for AppSync Event API
Based exactly on the working test_websocket_listener.py implementation
"""

import json
import time
import threading
import uuid
import logging
from datetime import datetime
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass
import os
from dotenv import load_dotenv

# WebSocket imports
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    raise ImportError("websocket-client not installed. Install with: pip install websocket-client")

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class EventMessage:
    """Represents a received event message"""
    channel: str
    event_data: Dict[str, Any]
    message_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    raw_message: Optional[str] = None


class WebSocketEventClient:
    """Production WebSocket client - exact copy of working EventListener pattern"""
    
    def __init__(self, http_domain: str = None, realtime_domain: str = None, api_key: str = None):
        """Initialize WebSocket Event Client - exact same as working listener"""
        # self.http_domain = http_domain or "kz477vlbgjclxbxmc7vhwpf2iq.appsync-api.us-east-1.amazonaws.com"
        # self.realtime_domain = realtime_domain or "kz477vlbgjclxbxmc7vhwpf2iq.appsync-realtime-api.us-east-1.amazonaws.com"
        # self.api_key = api_key or "da2-nnrztbsrgrb3zis7m7kq5m7wjy"
        
        self.http_domain = os.getenv("APPSYNC_HTTP_DOMAIN")
        self.realtime_domain = os.getenv("APPSYNC_REALTIME")
        self.api_key = os.getenv("APPSYNC_API_KEY")
        # State - exact same as working listener
        self.ws = None
        self.connected = False
        self.running = False
        self.message_count = 0
        self.subscriptions = {}
        
        # Threading
        self.listen_thread = None
        
        # Event callbacks for subscriptions
        self.event_callbacks: Dict[str, Callable[[EventMessage], None]] = {}
        
        # Statistics
        self.connection_start_time = None
        
        # Reconnection settings
        self.auto_reconnect = True
        self.max_reconnect_attempts = 5
        self.reconnect_count = 0
        self.reconnect_delay = 2.0
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def get_auth_protocol(self):
        """Get authentication protocol header - exact same as working listener"""
        authorization = {
            'x-api-key': self.api_key,
            'host': self.http_domain
        }
        
        import base64
        header = base64.b64encode(json.dumps(authorization).encode()).decode()
        header = header.replace('+', '-').replace('/', '_').rstrip('=')
        return f"header-{header}"
    
    def connect(self):
        """Connect to WebSocket - exact same as working listener"""
        with self.lock:
            if self.connected:
                logger.warning("Already connected")
                return True
            
            ws_url = f"wss://{self.realtime_domain}/event/realtime"
            subprotocols = ['aws-appsync-event-ws', self.get_auth_protocol()]
            
            logger.info(f"Connecting to: {ws_url}")
            logger.debug(f"Subprotocols: {subprotocols}")
            
            try:
                self.ws = websocket.WebSocket()
                self.ws.connect(ws_url, subprotocols=subprotocols)
                self.connected = True
                self.running = True
                self.connection_start_time = datetime.now()
                self.reconnect_count = 0
                
                logger.info("WebSocket connected successfully")
                
                # Start listening for messages - exact same as working listener
                self.listen_thread = threading.Thread(target=self._listen_for_messages, daemon=True)
                self.listen_thread.start()
                
                return True
                
            except Exception as e:
                logger.error(f"WebSocket connection failed: {e}")
                self.connected = False
                if self.auto_reconnect:
                    self._attempt_reconnect()
                return False
    
    def subscribe_to_channel(self, channel: str, callback: Callable[[EventMessage], None], subscription_id: str = None):
        """Subscribe to a channel - exact same as working listener"""
        if not self.connected:
            logger.error("Not connected to WebSocket")
            return None
        
        if not subscription_id:
            subscription_id = str(uuid.uuid4())
        
        # Store callback for this subscription
        self.event_callbacks[subscription_id] = callback
        
        message = {
            "id": subscription_id,
            "type": "subscribe",
            "channel": channel,
            "authorization": {
                "x-api-key": self.api_key
            }
        }
        
        logger.info(f"Subscribing to channel: {channel}")
        logger.debug(f"Subscription ID: {subscription_id}")
        
        try:
            self.ws.send(json.dumps(message))
            self.subscriptions[subscription_id] = {
                'channel': channel,
                'subscribed_at': datetime.now()
            }
            logger.info("Subscription request sent")
            return subscription_id
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            return None
    
    def unsubscribe(self, subscription_id: str):
        """Unsubscribe from a channel"""
        if subscription_id not in self.subscriptions:
            logger.warning(f"Subscription {subscription_id} not found")
            return False
        
        message = {
            "id": subscription_id,
            "type": "unsubscribe"
        }
        
        try:
            self.ws.send(json.dumps(message))
            del self.subscriptions[subscription_id]
            if subscription_id in self.event_callbacks:
                del self.event_callbacks[subscription_id]
            logger.info(f"Unsubscribed: {subscription_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")
            return False
    
    def publish_events(self, channel: str, events: List[Dict[str, Any]], message_id: str = None):
        """Publish events to a channel"""
        if not self.connected:
            logger.error("Not connected to WebSocket")
            return False
        
        if not message_id:
            message_id = str(uuid.uuid4())
        
        # Convert events to JSON strings
        json_events = [json.dumps(event) for event in events]
        
        message = {
            "id": message_id,
            "type": "publish",
            "channel": channel,
            "events": json_events,
            "authorization": {
                "x-api-key": self.api_key
            }
        }
        
        try:
            self.ws.send(json.dumps(message))
            logger.debug(f"Published {len(events)} events to {channel}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            return False
    
    def _listen_for_messages(self):
        """Listen for incoming WebSocket messages - exact same as working listener"""
        logger.debug("Started listening for messages")
        
        while self.running and self.connected:
            try:
                message = self.ws.recv()
                if message:
                    self.message_count += 1
                    timestamp = datetime.now()
                    
                    logger.debug(f"Received message #{self.message_count}: {message}")
                    
                    # Try to parse and handle JSON - exact same as working listener
                    try:
                        msg_data = json.loads(message)
                        msg_type = msg_data.get('type')
                        
                        if msg_type == 'connection_ack':
                            logger.info("Connection acknowledged")
                        elif msg_type == 'ka':
                            logger.debug("Keep-alive received")
                        elif msg_type == 'data':
                            self._handle_data_message(msg_data, message, timestamp)
                        elif msg_type == 'error':
                            logger.error(f"WebSocket error: {msg_data.get('payload', {})}")
                        elif msg_type == 'subscribe_success':
                            logger.info(f"Subscription confirmed: {msg_data.get('id')}")
                        elif msg_type == 'subscribe_error':
                            logger.error(f"Subscription error: {msg_data.get('id')} - {msg_data.get('payload', {})}")
                        
                    except json.JSONDecodeError:
                        logger.debug("Received non-JSON message")
                        
            except websocket.WebSocketConnectionClosedException:
                logger.warning("WebSocket connection closed")
                self.connected = False
                if self.auto_reconnect:
                    self._attempt_reconnect()
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                if self.running and self.auto_reconnect:
                    self._attempt_reconnect()
                break
        
        logger.debug("Stopped listening for messages")
    
    def _handle_data_message(self, msg_data: Dict, raw_message: str, timestamp: datetime):
        """Handle data message (events)"""
        subscription_id = msg_data.get('id')
        event_data = msg_data.get('event', {})
        
        if subscription_id in self.subscriptions and subscription_id in self.event_callbacks:
            subscription = self.subscriptions[subscription_id]
            callback = self.event_callbacks[subscription_id]
            
            # Create event message
            event_message = EventMessage(
                channel=subscription['channel'],
                event_data=event_data,
                message_id=subscription_id,
                timestamp=timestamp,
                raw_message=raw_message
            )
            
            try:
                callback(event_message)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
        else:
            logger.warning(f"Received data for unknown subscription: {subscription_id}")
    
    def _attempt_reconnect(self):
        """Attempt to reconnect"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            return
        
        self.reconnect_count += 1
        wait_time = self.reconnect_delay * self.reconnect_count
        
        logger.info(f"Attempting reconnection {self.reconnect_count}/{self.max_reconnect_attempts} in {wait_time}s")
        
        # Store current subscriptions and callbacks
        old_subscriptions = dict(self.subscriptions)
        old_callbacks = dict(self.event_callbacks)
        
        # Clean up current connection
        self.running = False
        self.connected = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None
        
        # Wait before reconnecting
        time.sleep(wait_time)
        
        # Attempt to reconnect
        if self.connect():
            logger.info("Reconnected successfully, resubscribing to channels...")
            
            # Wait a moment for connection to stabilize
            time.sleep(1)
            
            # Resubscribe to channels
            for sub_id, sub_info in old_subscriptions.items():
                if sub_id in old_callbacks:
                    self.subscribe_to_channel(
                        sub_info['channel'],
                        old_callbacks[sub_id],
                        sub_id
                    )
        else:
            logger.error(f"Reconnection attempt {self.reconnect_count} failed")
    
    def show_status(self):
        """Show current status - same as working listener"""
        status = {
            "connected": self.connected,
            "running": self.running,
            "messages_received": self.message_count,
            "active_subscriptions": len(self.subscriptions),
            "reconnect_count": self.reconnect_count
        }
        
        if self.connection_start_time:
            uptime = (datetime.now() - self.connection_start_time).total_seconds()
            status["uptime_seconds"] = uptime
        
        return status
    
    def get_subscriptions(self):
        """Get list of active subscriptions"""
        return [
            {
                'id': sub_id,
                'channel': info['channel'],
                'subscribed_at': info['subscribed_at'].isoformat()
            }
            for sub_id, info in self.subscriptions.items()
        ]
    
    def close(self):
        """Close WebSocket connection - exact same as working listener"""
        logger.info("Closing WebSocket connection")
        self.running = False
        self.connected = False
        
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None
        
        # Clear subscriptions and callbacks
        self.subscriptions.clear()
        self.event_callbacks.clear()
        
        logger.info("WebSocket connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.close()


# Convenience functions for common use cases

def create_event_client(
    http_domain: str = None,
    realtime_domain: str = None,
    api_key: str = None
) -> WebSocketEventClient:
    """
    Create a WebSocket event client with default settings
    
    Returns:
        WebSocketEventClient: Configured client instance
    """
    return WebSocketEventClient(http_domain, realtime_domain, api_key)


def simple_event_listener(
    channels: List[str],
    callback: Callable[[EventMessage], None],
    duration: Optional[float] = None
) -> WebSocketEventClient:
    """
    Simple event listener for multiple channels
    
    Args:
        channels: List of channels to subscribe to
        callback: Function to call for all events
        duration: How long to listen (None = indefinitely)
        
    Returns:
        WebSocketEventClient: Client instance
    """
    client = create_event_client()
    
    if client.connect():
        # Wait for connection to stabilize
        time.sleep(1)
        
        # Subscribe to all channels
        for channel in channels:
            client.subscribe_to_channel(channel, callback)
        
        # Listen for specified duration
        if duration:
            time.sleep(duration)
            client.close()
    
    return client


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    def event_handler(event: EventMessage):
        """Example event handler"""
        print(f"Received event on {event.channel}: {event.event_data}")
    
    # Example 1: Basic usage
    print("Example 1: Basic WebSocket client")
    client = create_event_client()
    
    if client.connect():
        # Subscribe to a channel
        client.subscribe_to_channel("/supervisor/*", event_handler)
        
        # Keep running for 30 seconds
        time.sleep(300)
        
        client.close()