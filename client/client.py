import websockets
from websockets.exceptions import ConnectionClosed
from itertools import cycle

import configs
import json
from sshtunnel import SSHTunnelForwarder


class Client(object):
    def __init__(self, host):
        self.current_node = list(filter(lambda v: v['host'] == host, configs.nodes))[0]
        self.another_nodes = list(filter(lambda v: v['host'] != host, configs.nodes))

    async def request(self, action: str):
        nodes = cycle([self.current_node] + self.another_nodes)

        if action == "update":
            msg = {
                'action': 'update',
                'var': input("What variable would you like to update? "),
                'value': input("What value do you want to assign to this variable? ")
            }
        elif action == "read":
            msg = {
                'action': 'read',
                'var': input("What variable would you like to read? "),
                'value': None
            }
        else:
            raise AssertionError("Unknown request action.")

        while True:
            node = nodes.__next__()

            ssh_tunnel = SSHTunnelForwarder(
                node['host'],
                ssh_username=node['username'],
                ssh_password=node['password'],
                remote_bind_address=("127.0.0.1", node['port']))
            ssh_tunnel.start()

            try:
                url = f"ws://127.0.0.1:{ssh_tunnel.local_bind_port}"

                async with websockets.connect(url) as ws:
                    await ws.send(json.dumps(msg))
                    print(json.loads(await ws.recv()))

                ssh_tunnel.close()
                break
            except ConnectionClosed:
                continue

    async def listen(self):
        while True:
            action = input("What operation would you like to perform? (type read or update) ").lower()
            if action == 'read':
                await self.request(action="read")
            elif action == 'update':
                await self.request(action="update")
            elif action == "exit":
                break
            else:
                print("You are dummy.")
