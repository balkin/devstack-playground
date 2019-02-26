import json
import socketserver
from http.server import BaseHTTPRequestHandler
import mysql.connector

PORT = 8000

# Handler = http.server.SimpleHTTPRequestHandler
# Запустить пару виртуальных машин (можно 2)
# Из базы достать: 
# SELECT uuid, display_name from instances where vm_state = 'active'
# SELECT mac_address, device_id from ports
# Написать HTTP сервис, который выдает следующий json: [
# {
# instance_id: «xxxxxx»,
# interfaces: [
#  «mac_address»
# ]
# }
# ]
#

conn = mysql.connector.connect(user='root', password='Passw0rd', database='nova_cell1')
query1 = "SELECT uuid, display_name from instances where vm_state = 'active'"
query2 = "SELECT mac_address, device_id from ports"


class OpenstackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = []

        mycursor = conn.cursor()
        mycursor.execute(query1)
        for x in mycursor.fetchall():
            # Пишу как явист без list comprehensions, но потом отрефакторю по-питоньи
            entry = {"instance_id": x[0], "interfaces": []}
            response.append(entry)

        self.wfile.write(bytes(json.dumps(response), 'utf8'))


# with почему-то не работает =(
httpd = socketserver.TCPServer(("", PORT), OpenstackHandler)
print("Listening on {}".format(PORT))
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print("Server stopped on keyboard interrupt")
finally:
    httpd.server_close()

print("DONE")
