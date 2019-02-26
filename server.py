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
query_instances = "SELECT uuid, display_name from instances where vm_state = 'active'"
query_ports = "SELECT mac_address, device_id from neutron.ports"

# TODO: Refactor it
ports_dict = {}
ports_cursor = conn.cursor()

try:
    ports_cursor.execute(query_ports)

    for (mac_address, device_id) in ports_cursor:
        if device_id in ports_dict:
            ports_dict[device_id].append(mac_address)
        else:
            ports_dict[device_id] = [mac_address]

finally:
    ports_cursor.close()

class OpenstackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Send response status code
        self.send_response(200)

        # Send headers
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = []

        instances_cursor = conn.cursor()
        try:
            instances_cursor.execute(query_instances)
            for (uuid, display_name) in instances_cursor.fetchall():
                # Пишу как явист без list comprehensions, но потом отрефакторю по-питоньи
                entry = {"instance_id": uuid, "interfaces": ports_dict[uuid]}
                response.append(entry)
        finally:
            instances_cursor.close()

        self.wfile.write(bytes(json.dumps(response, indent=True), 'utf8'))


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
