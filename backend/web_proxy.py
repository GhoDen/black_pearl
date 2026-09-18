import asyncio
import websockets
import sys
import os

# --- Configuration ---
# The host and port where the WebSocket server will listen for browser connections.
# This should remain "localhost" because the Tor daemon handles external traffic
# and forwards it to this local port.
WS_HOST = "localhost"
WS_PORT = 8000

# The default target host and port for the raw TCP connection (the service you want to expose).
# IMPORTANT: Change TARGET_PORT to 23 for Telnet, as requested.
TARGET_HOST = "localhost"
TARGET_PORT = 2323 # Changed from 9000 to 23
TEST_ECHO_PORT = 9000
# ---------------------

async def tcp_to_ws_relay(tcp_reader, websocket):
    """
    Relays data from the TCP socket back to the WebSocket client (browser).
    Sends raw bytes as binary WebSocket frames to preserve binary fidelity.
    """
    try:
        while True:
            # Read a chunk of data from the TCP connection
            data = await tcp_reader.read(125000000)#65536)  # Increased to 64KB to match main.py's chunk size
            if not data:
                print(f"[TCP] Target closed connection.")
                break
            
            # Send the received data over the WebSocket as binary frame
            await websocket.send(data)
            print(f"[WS SENT BIN] {len(data)} bytes to client")

    except websockets.exceptions.ConnectionClosedOK:
        print("[WS] Client closed connection during TCP read.")
    except Exception as e:
        print(f"[ERROR] TCP to WS relay failed: {e}")
    finally:
        # Ensure the WebSocket is closed if an error occurred
        if websocket.open:
            await websocket.close()

async def ws_to_tcp_relay(tcp_writer, websocket):
    """
    Relays data from the WebSocket client (browser) to the TCP socket.
    Accepts both text and binary WS frames.
    """
    try:
        async for message in websocket:
            # If message is bytes (binary frame), forward as-is
            if isinstance(message, (bytes, bytearray, memoryview)):
                tcp_writer.write(bytes(message))
                sent_len = len(message)
            else:
                # Text frame: encode to UTF-8
                encoded = message.encode('utf8')
                tcp_writer.write(encoded)
                sent_len = len(encoded)
            await tcp_writer.drain()
            print(f"[TCP SENT] {sent_len} bytes from client")

    except websockets.exceptions.ConnectionClosedOK:
        print("[WS] Client closed connection.")
    except Exception as e:
        print(f"[ERROR] WS to TCP relay failed: {e}")

async def proxy_handler(websocket, path=None):
    """
    Handles a single incoming WebSocket connection.
    This function establishes the TCP connection and starts the relays.
    """
    path_info = path if path is not None else "N/A"
    print(f"\n[WS ACCEPTED] New connection from client on path: {path_info}")
    
    tcp_reader = None
    tcp_writer = None

    try:
        # 1. Establish the raw TCP connection to the target
        print(f"[TCP CONNECTING] Attempting to connect to {TARGET_HOST}:{TARGET_PORT}...")
        tcp_reader, tcp_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
        print(f"[TCP CONNECTED] Successfully connected to target.")

        # 2. Start bidirectional relays concurrently
        # The connection remains open until one of these tasks completes (e.g., connection closes)
        await asyncio.gather(
            tcp_to_ws_relay(tcp_reader, websocket),
            ws_to_tcp_relay(tcp_writer, websocket),
            return_exceptions=True  # Allows one task to fail without stopping the other immediately
        )

    except ConnectionRefusedError:
        error_msg = f"[ERROR] TCP connection refused by {TARGET_HOST}:{TARGET_PORT}. Target service may not be running or accessible."
        print(error_msg)
        await websocket.send(f"[SYSTEM ERROR] {error_msg}")
    except Exception as e:
        error_msg = f"[FATAL ERROR] Proxy failed: {e.__class__.__name__}: {e}"
        print(error_msg)
        # Send a brief error to the client before closing the connection
        try:
            await websocket.send(f"[SYSTEM ERROR] Proxy closed due to internal failure: {e.__class__.__name__}")
        except:
            pass # Ignore if we can't send the error
        finally:
            # Ensure the WebSocket closes properly after the fatal error
            if websocket.open:
                await websocket.close(code=1011, reason=f"Proxy failure: {e.__class__.__name__}")


    finally:
        # 3. Clean up the TCP connection
        if tcp_writer:
            print("[TCP CLOSING] Closing TCP connection.")
            try:
                tcp_writer.close()
                await tcp_writer.wait_closed()
            except Exception as e:
                print(f"[ERROR] Error closing TCP writer: {e}")

        print("[WS CLOSED] Client session ended.")

# --- Test TCP Echo Server Function ---

async def handle_echo(reader, writer):
    """Simple handler for the TCP echo server."""
    addr = writer.get_extra_info('peername')
    print(f"[ECHO SERVER] Connection established from {addr}")
    # Use the configured port for the welcome message
    writer.write(f"Welcome to the Echo Test Server on port {TEST_ECHO_PORT}! Type anything to get an echo.\n".encode('utf8'))
    await writer.drain()

    try:
        while True:
            data = await reader.read(100)
            if not data:
                break
            message = data.decode().strip()
            print(f"[ECHO SERVER] Received: {message}")
            
            response = f"Echo: {message}\n"
            writer.write(response.encode('utf8'))
            await writer.drain()
    except ConnectionResetError:
        pass # Client closed connection abruptly
    except Exception as e:
        print(f"[ECHO SERVER] Handler error: {e}")
    finally:
        print(f"[ECHO SERVER] Closing connection from {addr}")
        writer.close()
        await writer.wait_closed()


async def main():
    """
    Starts the WebSocket server and the optional Test Echo Server.
    """
    print("=" * 60)
    print("WebSocket-TCP Proxy Server starting...")
    print(f"WS Address: ws://{WS_HOST}:{WS_PORT}/<path>")
    print(f"TCP Target: {TARGET_HOST}:{TARGET_PORT}")
    print("=" * 60)

    # Start the optional test echo server concurrently
    # Note: If the target port is 23 (Telnet), you probably don't need this echo server,
    # but I'm leaving it for a complete example.
    echo_server = await asyncio.start_server(
        handle_echo, 'localhost', TEST_ECHO_PORT
    )
    addr = echo_server.sockets[0].getsockname()
    print(f"[SYSTEM] TCP Echo Server started on {addr}")

    # Start the main WebSocket proxy server
    async with websockets.serve(proxy_handler, WS_HOST, WS_PORT):
        # Run until the process is manually stopped
        await asyncio.Future()

if __name__ == "__main__":
    try:
        # Check if websockets is installed
        if 'websockets' not in sys.modules:
            print("\n[SETUP REQUIRED] The 'websockets' library is not installed.")
            print("Please install it using: pip install websockets\n")
            sys.exit(1)

        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shutting down gracefully.")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn unhandled error occurred: {e}")
        sys.exit(1)