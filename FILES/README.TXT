                          Black Pearl File Server
                          =======================

A telnet/netcat file server for secure file sharing through Tor network.

CONNECTION
----------
To connect:
    torsocks netcat <address.onion> 23

COMMANDS
--------
Available commands after connecting:
    DIR <path>         List files in directory
    DOWNLOAD <file>    Download a specific file
    CONTACT <msg>      Leave a message for the developers
    EXIT              Close the connection

DOWNLOADING FILES - WARNING: Doesn't work as advertised yet. :-/
-----------------
Two methods available depending on file size:

1. For Large Files (>100KB):
   Streams directly to disk without display:

echo "DOWNLOAD <file>" | torsocks netcat <address.onion> 2323 | \
 perl -ne 'BEGIN{undef $/} \
 if(/_FILE_START_TAG_RJcGYETKFodguvnd@G8djEWwL86Pivicmb89yW@Zm@JiTRkm62wg\
 (.+?)_FILE_END_TAG_-G4p8_atmWgCuW3wvYaE@teZcp3Hx!N7_f_n\*\*8wDP\*HdQ\.y-qkn/s)\
 {print $1}' > OUTPUT

2. For Small Files:
   Allows interaction with service before download:

 torsocks netcat <address.onion> 2323 | \
 tee >(perl -ne 'BEGIN{undef $/} \
 if(/_FILE_START_TAG_RJcGYETKFodguvnd@G8djEWwL86Pivicmb89yW@Zm@JiTRkm62wg\
 (.+?)_FILE_END_TAG_-G4p8_atmWgCuW3wvYaE@teZcp3Hx!N7_f_n\*\*8wDP\*HdQ\.y-qkn/s)\
 {print $1}' > OUTPUT)

   Note: Press [Enter] when the screen stops updating to complete download.

WEB INTERFACE
-------------
A browser-based interface is available on port 9000:
- Easy file browsing and downloading
- Real-time connection status
- Terminal-like interface
- Automatic file marker handling

File markers and download commands not needed when using web interface.

SECURITY
--------
- All connections through Tor (use torsocks)
- Protected against directory traversal
- Safe binary file transfers
- Secure WebSocket communication

UPDATES
-------
New content added every Saturday - check back weekly!

Share with your friends!