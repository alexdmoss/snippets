from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException

'''
This code was originally used - but deleting nodes does not terminate underlying compute instances
'''


def list_preemptible_nodes_by_creation_time(v1):
    logger.debug("Listing nodes")
    nodes = list()
    response = list_nodes(v1)
    for item in response.items:
        nodes.append((get_time_as_seconds_since_epoch(item.metadata.creation_timestamp), item.metadata.name))
    # returns list sorted by creation_time oldest(lowest) --> newest(highest)
    nodes.sort()
    return nodes


def list_nodes(v1):
    try:
        return v1.list_node(watch=False, timeout_seconds=50, label_selector="cloud.google.com/gke-preemptible=true")
    except ApiException as e:
        logger.error(f"Exception when calling CoreV1Api->list_node: {e}")


def delete_node(node: str, v1):
    logger.debug(f"Deleting node {node}")
    try:
        response = v1.delete_node(node, grace_period_seconds=50)
        if response["status"] == "Success":
            logger.info(f"Node {node} scheduled for deletion")
        else:
            logger.warning(f"Non-success status returned. Full response was: {response}")
    except ApiException as e:
        logger.error(f"Exception when calling CoreV1Api->delete_node: {e}")


def create_k8s_client():
    try:
        config.load_incluster_config()                                             # on cluster
    except ConfigException:
        logger.warning("Running using local credentials")
        config.load_kube_config(os.path.join(os.environ["HOME"], '.kube/config'))  # fallback running locally
    return client.CoreV1Api()


def find_nodes_to_restart(nodes) -> str:
    # if the current node is within 1 hour of next node, cycle the current node and break (eventual consistency)
    logger.debug("Looking for nodes which are close to creation times of other nodes")
    # this is not very pythonic!
    i = 0
    for creation_time, node in nodes:
        i = i + 1
        try:
            next_creation_time = nodes[i][0]
        except IndexError:
            next_creation_time = strftime("%s", gmtime())
        interval = int(next_creation_time) - int(creation_time)
        logger.debug(f"For Node {node}, comparing {next_creation_time} to {creation_time} = {interval}")
        if interval <= 3600:
            logger.debug(f"{node} will be deleted")
            return node
