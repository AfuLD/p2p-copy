# import the needed functions from the api, maybe alias them
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy_server import run_relay
imported_functions = api_send, api_receive, run_relay


# alternatively just import the modules and refer accordingly
import p2p_copy, p2p_copy_server
imported_module_functions = p2p_copy.send, p2p_copy.receive, p2p_copy_server.run_relay


assert imported_functions == imported_module_functions, "Error: functions are different"

