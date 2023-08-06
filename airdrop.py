from snapshot import create_average_snapshot, get_chain_and_contract
import indexer
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
import time
import json
from config import load_config, get_excluded_address, get_rpc
import os
import asyncio
import dotenv

cfg = load_config()
dotenv.load_dotenv()

# Constants, 1 week schedule
CHUNK_SIZE = 100
SCHEDULE_INTERVAL = 604800
MAX_RETRIES = 5
TAX_WALLET_ADDRESS = os.getenv('TAX_WALLET_ADDRESS')  # Address of the tax wallet
TAX_WALLET_PRIVATE_KEY = os.getenv('TAX_WALLET_PRIVATE_KEY')  # Private key of the tax wallet

LAST_AIRDROPPED_BLOCKS_FILE = 'last_airdropped_blocks.json'

def get_last_airdropped_block(chain_id, contract_address):
    if os.path.isfile(LAST_AIRDROPPED_BLOCKS_FILE):
        with open(LAST_AIRDROPPED_BLOCKS_FILE, 'r') as file:
            last_airdropped_blocks = json.load(file)
            return last_airdropped_blocks.get(str(chain_id), {}).get(contract_address)
    else:
        return 0


def set_last_airdropped_block(chain_id, contract_address, block_number):
    last_airdropped_blocks = {}
    if os.path.isfile(LAST_AIRDROPPED_BLOCKS_FILE):
        with open(LAST_AIRDROPPED_BLOCKS_FILE, 'r') as file:
            last_airdropped_blocks = json.load(file)
    if str(chain_id) not in last_airdropped_blocks:
        last_airdropped_blocks[str(chain_id)] = {}
    last_airdropped_blocks[str(chain_id)][contract_address] = block_number
    with open(LAST_AIRDROPPED_BLOCKS_FILE, 'w') as file:
        json.dump(last_airdropped_blocks, file)


def get_last_run():
    if os.path.isfile('last_run.txt'):
        with open('last_run.txt', 'r') as file:
            return int(file.read())
    else:
        return 0


def set_last_run(timestamp): 
    with open('last_run.txt', 'w') as file:
        file.write(str(timestamp))


def get_abi(chain_id, contract_address):
    path = f'abi/{chain_id}_{contract_address}.abi.json'
    if os.path.isfile(path):
        with open(path, 'r') as file:
            return json.load(file)
    else:
        with open('erc20.abi.json', 'r') as file:
            return json.load(file)
    

def get_snapshot(chain_id, contract_address, end_block):
    # get excluded addresses from config.yml chains->contracts->excluded_addresses
    excluded_addresses = get_excluded_address(chain_id, contract_address)

    # get the last airdropped block for this contract and add 1
    start_block = get_last_airdropped_block(chain_id, contract_address) + 1
    
    # return the snapshot, excluding liquidity pools
    balances = create_average_snapshot(chain_id, contract_address, start_block, end_block)

    return {address: balance for address, balance in balances.items() if address not in excluded_addresses}


def eligible_balance_for_airdrop(chain_id, contract_address):
    abi = get_abi(chain_id, contract_address)
    rpc = get_rpc(chain_id)
    w3 = Web3(HTTPProvider(rpc))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    contract = w3.eth.contract(address=contract_address, abi=abi)

    # Get the balance of the wallet
    current_balance = contract.functions.balanceOf(TAX_WALLET_ADDRESS).call()

    transactions_file = f'{contract_address}_{chain_id}_transactions.json'
    failed_sum = 0

    # If the transaction file exists, compute the sum of failed transfers
    if os.path.isfile(transactions_file):
        with open(transactions_file, 'r') as file:
            transactions_log = json.load(file)

        for txn_id, txn_info in transactions_log.items():
            if txn_info['status'] == 'failed':
                failed_sum += sum(txn_info['balances'])

    # Return the balance eligible for airdrop
    return current_balance - failed_sum


def distribute_airdrop(chain_id, contract_address, snapshot):
    abi = get_abi(chain_id, contract_address)
    rpc = get_rpc(chain_id)
    w3 = Web3(HTTPProvider(rpc))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)    
    contract = w3.eth.contract(address=contract_address, abi=abi)
    nonce = w3.eth.get_transactionCount(TAX_WALLET_ADDRESS)
    snapshot_total = sum(snapshot.values())
    wallet_balance = eligible_balance_for_airdrop(chain_id, contract_address)

    addresses = list(snapshot.keys())
    balances = [int(snapshot[address] / snapshot_total * wallet_balance) for address in addresses]

    transactions_file = f'{contract_address}_{chain_id}_transactions.json'

    # Load the transactions log file if it exists, otherwise start with an empty dict.
    if os.path.isfile(transactions_file):
        with open(transactions_file, 'r') as file:
            transactions_log = json.load(file)
    else:
        transactions_log = {}

    while addresses:
        chunk_addresses = addresses[:CHUNK_SIZE]
        chunk_balances = balances[:CHUNK_SIZE]

        addresses = addresses[CHUNK_SIZE:]
        balances = balances[CHUNK_SIZE:]

        txn = contract.functions.airdrop(chunk_addresses, chunk_balances).build_transaction({
            'chainId': chain_id,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
        })

        txn['gas'] = w3.eth.estimate_gas(txn)
        signed_txn = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
        print(f'Sending to {len(chunk_addresses)} addresses...')
        
        # Generate a unique ID for this transaction
        txn_id = str(uuid.uuid4())
        transactions_log[txn_id] = {
            'status': 'pending',
            'addresses': chunk_addresses,
            'balances': chunk_balances,
            'transaction_hash': None,
            'retry': 0
        }
        
        try:
            txn_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            transactions_log[txn_id]['transaction_hash'] = txn_hash.hex()
            
            receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

            # Check transaction status
            if receipt['status'] == 0:
                print("Transaction failed!")
                transactions_log[txn_id]['status'] = 'failed'
                continue
            else:
                transactions_log[txn_id]['status'] = 'success'

        except Exception as e:
            print(f"Failed to send transaction: {str(e)}")
            transactions_log[txn_id]['status'] = 'failed'
            transactions_log[txn_id]['retry'] += 1
            continue

        nonce += 1

        # Save the transactions log after each transaction
        with open(transactions_file, 'w') as file:
            json.dump(transactions_log, file)


def retry_failed_chunks(chain_id, contract_address):
    transactions_file = f'{contract_address}_{chain_id}_transactions.json'
    if os.path.isfile(transactions_file):
        with open(transactions_file, 'r') as file:
            transactions_log = json.load(file)

        for txn_id, txn_info in transactions_log.items():
            if txn_info['status'] == 'failed' and txn_info['retry'] < MAX_RETRIES:
                print(f'Retrying transaction {txn_id}')
                distribute_airdrop(chain_id, contract_address, dict(zip(txn_info['addresses'], txn_info['balances'])))
            elif txn_info['status'] == 'failed' and txn_info['retry'] >= MAX_RETRIES:
                print(f'Failed to send transaction {txn_id} after {MAX_RETRIES} attempts')
    else:
        print('No transaction log file found.')


def run_snapshot_and_airdrop():
    for chain in cfg['chains']:
        for contract in chain['contracts']:
            retry_failed_chunks(chain['id'], contract['address'])
            print(f'Running snapshot and airdrop for {contract["address"]} on chain {chain["id"]}')
            endblock = indexer.get_last_processed_block(chain['id'], contract['address'])
            snapshot = get_snapshot(chain['id'], contract['address'], endblock)
            distribute_airdrop(chain['id'], contract['address'], snapshot)
            set_last_airdropped_block(chain['id'], contract['address'], endblock)


if(__name__ == '__main__'):
    # update the indexer if we haven't done so in a while
    last_run = get_last_run()
    if time.time() - last_run > 3600:
        print('Updating indexer...')
        asyncio.run(indexer.index())
    else:
        print('Indexer is up to date.')

    # run the snapshot for each chain and performe the airdrop
    if time.time() - last_run > SCHEDULE_INTERVAL:
        print('Running snapshot and airdrop...')
        run_snapshot_and_airdrop()
        set_last_run(time.time())
    else:
        print('Airdrop is not scheduled yet.')
    