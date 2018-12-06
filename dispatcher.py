import argparse
import websockets
import configs
import asyncio

from client import Client
from client.client_2 import Client as ClientV2

from middleware import Node

parser = argparse.ArgumentParser()
parser.add_argument('--script', help="Script to run.", required=True)
parser.add_argument("--host", required=True)

if __name__ == "__main__":
    args = parser.parse_args()

    if args.script == "server":
        host = args.host
        node = Node(host=host)

        node_params = list(filter(lambda v: v['host'] == host, configs.nodes))[0]
        server = websockets.serve(node.listener, host="127.0.0.1", port=node_params['port'])

        asyncio.get_event_loop().run_until_complete(server)
        asyncio.get_event_loop().run_forever()

    elif args.script == "client":
        host = args.host
        client = Client(host=host)
        asyncio.get_event_loop().run_until_complete(client.listen())

    elif args.script == "clientV2":
        host = args.host
        client = ClientV2(host=host)
        asyncio.get_event_loop().run_until_complete(client.start())
