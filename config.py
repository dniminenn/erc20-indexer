import yaml

def load_config():
    with open("config.yml", 'r') as ymlfile:
        return yaml.safe_load(ymlfile)

def get_excluded_address(chain_id, contract_address):
    cfg = load_config()
    for chain in cfg['chains']:
        if chain['id'] == chain_id:
            for contract in chain['contracts']:
                if contract['address'] == contract_address:
                    return contract['excluded_addresses']
            break
    return []

def get_rpc(chain_id):
    cfg = load_config()
    for chain in cfg['chains']:
        if chain['id'] == chain_id:
            return chain['rpc_url']
    return None