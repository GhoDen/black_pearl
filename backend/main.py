import socket
import os
import sys
import threading
from pathlib import Path

# Configuration
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 2323       # Telnet port alternative
FILE_DIR = 'FILES'  # Directory where files are stored
CONTACT_DIR = 'MESSAGES'  # Directory to store contact messages

# File transfer markers (change here if you want different delimiters)
FILE_BEGIN_MARKER = b"_FILE_START_TAG_RJcGYETKFodguvnd@G8djEWwL86Pivicmb89yW@Zm@JiTRkm62wg"
FILE_END_MARKER = b"_FILE_END_TAG_-G4p8_atmWgCuW3wvYaE@teZcp3Hx!N7_f_n**8wDP*HdQ.y-qkn"

def is_safe_path(base_path: str, requested_path: str) -> bool:
    """
    Validate that the requested path is within the base path.
    Prevents directory traversal attacks.
    """
    try:
        # Convert paths to absolute and resolve any symlinks
        base_path = os.path.abspath(base_path)
        requested_full_path = os.path.abspath(os.path.join(base_path, requested_path))
        
        # Check if the requested path starts with the base path
        return os.path.commonpath([base_path]) == os.path.commonpath([base_path, requested_full_path])
    except Exception:
        return False


def setup_directory():
	"""Ensures the directory for serving files exists."""
	if not os.path.exists(FILE_DIR):
		try:
			os.makedirs(FILE_DIR)
			print(f"Created file directory: {FILE_DIR}")
		except OSError as e:
			print(f"Error creating directory {FILE_DIR}: {e}")
			sys.exit(1)

def send_binary_file(conn, file_path):
	"""Sends a file in raw binary mode, wrapped by BEGIN/END markers.

	Protocol (simple):
		BEGIN<raw file bytes>END

	Markers are defined by FILE_BEGIN_MARKER / FILE_END_MARKER constants.
	No length prefix, so the receiver must look for the END marker.
	"""
	try:
		with open(file_path, 'rb') as f:
			# Announce start of file transfer (marker followed by newline to reduce false-positive in text)
			conn.sendall(FILE_BEGIN_MARKER)
			while True:
				chunk = f.read(125000000)#65536)  # Increased to 64KB for better throughput
				if not chunk:
					break
				conn.sendall(chunk)
			# Explicit end marker
			conn.sendall(FILE_END_MARKER)
		return True
	except FileNotFoundError:
		return False
	except Exception as e:
		print(f"Error transferring binary file: {e}")
		return False


def handle_client(conn, addr, skip_intro=False):
	"""Handles a single client connection."""
	print(f"Connection established from {addr}")

	# Telnet intro banner
	crash = False	
	if os.path.exists(os.path.join("PAGES", "INTRO.TXT")):
		intro_text = open(os.path.join("PAGES", "INTRO.TXT"), 'r', encoding='utf-8', errors='ignore').read()
	else:
		intro_text = "Black Pearl is currently under maintenance.\n"
		crash = True
	if not skip_intro:
		conn.sendall(intro_text.encode())
	conn.sendall(b"\nCMD> ")
	if crash:
		conn.close()
		return

	try:
		request_bytes = conn.recv(1024)
		if not request_bytes:
			return

		request = request_bytes.decode('utf-8', errors='ignore').strip()
		command_parts = request.split(maxsplit=1)  # Split only on first whitespace to preserve spaces in path

		# --- DIR MODE ---
		if command_parts and command_parts[0].upper() == 'DIR':
			# If no subdirectory provided, list the contents of FILE_DIR
			if len(command_parts) == 1:
				requested_path = FILE_DIR
				print(f"Received DIR request for base directory: {requested_path}")
			else:
				# Get the directory path and remove any surrounding quotes if present
				dir_path = command_parts[1].strip('"\'')
				
				# Security check for directory traversal
				if not is_safe_path(FILE_DIR, dir_path):
					response = "Error: Invalid directory path.\n"
					conn.sendall(response.encode('utf-8'))
					handle_client(conn, addr, skip_intro=True)
					return
					
				requested_path = os.path.join(FILE_DIR, dir_path)
				print(f"Received DIR request for: {requested_path}")

			if os.path.exists(requested_path) and os.path.isdir(requested_path):
				files = os.listdir(requested_path)
				if files:
					file_list = []
					for filename in files:
						full_path = os.path.join(requested_path, filename)
						if os.path.isfile(full_path):
							size = os.path.getsize(full_path)
							file_list.append(f"{filename} ({size:,} bytes)")
						else:
							file_list.append(f"{filename}/ (DIR)")
					response = "\n".join(file_list) + "\n"
				else:
					response = "Directory is empty.\n"
			else:
				# If no subdir was provided, FILE_DIR should exist (created at startup)
				# but handle the case gracefully anyway
				if len(command_parts) == 1:
					response = f"Error: Base directory '{FILE_DIR}' not found.\n"
				else:
					response = f"Error: Directory '{dir_path}' not found.\n"

			conn.sendall(response.encode('utf-8'))
			handle_client(conn, addr, skip_intro=True)
			return

		# --- DOWNLOAD MODE ---
		if command_parts and command_parts[0].upper() == 'DOWNLOAD':
			if len(command_parts) == 1:
				conn.sendall("Error: No file specified for download.\n".encode('utf-8'))
				handle_client(conn, addr, skip_intro=True)
				return

			file_path = command_parts[1].strip('"\'')  # Remove any surrounding quotes
			# Security check for directory traversal
			if not is_safe_path(FILE_DIR, file_path):
				conn.sendall("Error: Invalid file path.\n".encode('utf-8'))
				handle_client(conn, addr, skip_intro=True)
				return

			requested_file = os.path.basename(file_path)
			file_path = os.path.join(FILE_DIR, file_path)
			print(f"Received DOWNLOAD request for: {requested_file}")

			if send_binary_file(conn, file_path):
				print(f"Successfully sent raw data for {requested_file}")
				handle_client(conn, addr, skip_intro=True)
			else:
				# Inform the client explicitly when the file doesn't exist or couldn't be sent
				print(f"File not found for DOWNLOAD: {requested_file}")
				conn.sendall(f"Error: File '{requested_file}' not found.\n".encode('utf-8'))
			return

		# --- CONTACT MODE ---
		if command_parts and command_parts[0].upper() == 'CONTACT':
			# Save new message in CONTACT_DIR
			if len(command_parts) == 1:
				conn.sendall("Error: No message provided for contact.\n".encode('utf-8'))
				handle_client(conn, addr, skip_intro=True)
				return
			message = command_parts[1]
			try:
				if not os.path.exists(CONTACT_DIR):
					os.makedirs(CONTACT_DIR)
				message_file = os.path.join(CONTACT_DIR, f"message_{addr[0]}_{addr[1]}.txt")
				
				# Check if file exists - if so, add separator before new message
				separator = "\n=== NEW MESSAGE ===\n" if os.path.exists(message_file) else ""
				
				with open(message_file, 'a', encoding='utf-8') as f:
					f.write(f"{separator}{message}\n")
					
				conn.sendall(b"Message received. Thank you for contacting us.\n")
				print(f"Saved contact message from {addr} to {message_file}")
				handle_client(conn, addr, skip_intro=True)
				return
			except Exception as e:
				print(f"Error saving contact message: {e}")
				conn.sendall(b"Error: Could not save your message.\n")
				handle_client(conn, addr, skip_intro=True)
				return

		# --- EXIT MODE ---
		if command_parts and command_parts[0].upper() == 'EXIT':
			conn.sendall(b"Goodbye. Tell your friends!\n")
			conn.close()
			print(f"Client {addr} requested disconnect")
			return

		# --- UNKNOWN COMMAND ---
		conn.sendall(b"Error: Unknown command.\n")
		handle_client(conn, addr, skip_intro=True)
		return

	except Exception as e:
		print(f"An error occurred: {e}")
	finally:
		conn.close()
		print(f"Connection closed for {addr}")


def start_server():
    """Starts the Telnet server and listens for connections."""
    setup_directory()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"Telnet File Server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            # Create a new thread for each client connection
            client_thread = threading.Thread(target=handle_client, args=(conn, addr))
            client_thread.daemon = True  # Thread will exit when main program exits
            client_thread.start()
            print(f"New thread started for client {addr}")

    except KeyboardInterrupt:
        print("\nServer shutting down.")
    except Exception as e:
        print(f"Failed to start server: {e}")
    finally:
        s.close()

if __name__ == "__main__":
	start_server()