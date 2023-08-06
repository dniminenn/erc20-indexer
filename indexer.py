import asyncio
import json
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
from concurrent.futures import ThreadPoolExecutor
from database import init_db, Chain, Contract, Event
from config import load_config

cfg = load_config()

w3executor = ThreadPoolExecutor(max_workers=10)

Session = init_db()

try:
    with open('erc20.abi.json') as f:
        abi = json.load(f)
except FileNotFoundError:
    raise Exception('ABI file not found: erc20.abi.json')

async def get_event_data(contract, start_block, end_block, web3):
    try:
        print(f"Getting events for {contract['contract'].address} from {start_block} to {end_block}")
        loop = asyncio.get_event_loop()

        transfer_signature = Web3.keccak(text="Transfer(address,address,uint256)").hex()

        # Define the filter parameters
        filter_params = {
            "fromBlock": start_block,
            "toBlock": end_block,
            "address": contract['contract'].address,
            "topics": [transfer_signature]
        }

        # Get the logs using eth_getLogs
        logs = await loop.run_in_executor(w3executor, lambda: web3.eth.get_logs(filter_params))

        # Parse the logs
        entries = [contract['contract'].events.Transfer().process_log(log) for log in logs]

        return entries

    except Exception as exc:
        print(f"Error getting events for {contract['contract'].address} from {start_block} to {end_block}: {exc}")
        raise


def setup_web3(chain_cfg):
    # Set up web3 instance
    w3 = Web3(HTTPProvider(chain_cfg['rpc_url']))

    # This line is necessary for some networks (like Rinkeby)
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # Create and commit Chain object
    db_session = Session()
    chain = db_session.query(Chain).filter_by(id=chain_cfg['id']).first()
    if chain is None:
        chain = Chain(id=chain_cfg['id'], name=chain_cfg['name'])
        db_session.add(chain)
        db_session.commit()

    contracts = []
    for contract_cfg in chain_cfg['contracts']:
        # Set up the contract
        contract_address = w3.to_checksum_address(contract_cfg['address'])
        contract_obj = w3.eth.contract(address=contract_address, abi=abi)

        # Query existing contract from the database
        db_contract = db_session.query(Contract).filter_by(address=contract_address).first()
        if db_contract is None:
            print(f"Adding new contract {contract_address}")
            last_processed_block = contract_cfg.get('startblock', 0) - 1
            name = contract_cfg.get('name', None)
            contract_db = Contract(
                name=name,
                address=contract_address,
                chain_id=chain.id,
                last_processed_block=last_processed_block
            )
            db_session.add(contract_db)
            db_session.commit()
        else:
            print(f"Found existing contract {contract_address}")
            contract_db = db_contract

        contract_dict = {'contract': contract_obj, 'db_contract': contract_db}
        contracts.append(contract_dict)

    return w3, contracts, db_session


def get_last_processed_block(chain, contract):
    db_session = Session()
    db_contract = db_session.query(Contract).filter_by(address=contract).first()
    if db_contract is None:
        return 0
    else:
        return db_contract.last_processed_block
    db.session.close()


async def process_chain(chain):
    web3, contracts, db_session = setup_web3(chain)
    chunk_size = chain['chunk_size']

    for contract in contracts:
        start_block = contract['db_contract'].last_processed_block + 1

        while start_block <= web3.eth.block_number:
            end_block = min(start_block + chunk_size - 1, web3.eth.block_number)
            events = await get_event_data(contract, start_block, end_block, web3)

            # Insert events into the database
            for event in events:
                db_event = Event(
                    contract_id=contract['db_contract'].id,
                    from_address=event['args']['from'],
                    to_address=event['args']['to'],
                    value=str(event['args']['value']),
                    block_number=event['blockNumber'],
                    transaction_hash=event['transactionHash'].hex(),
                )
                db_session.add(db_event)

            contract['db_contract'].last_processed_block = end_block
            db_session.commit()

            # Update the block range
            start_block = end_block + 1

        db_session.close()



async def index():
    await asyncio.gather(*(process_chain(chain) for chain in cfg['chains']))

if __name__ == "__main__":
    try:
        asyncio.run(index())
    except KeyboardInterrupt:
        print("\nExiting gracefully...")