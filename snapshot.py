from database import init_db, Event, Contract, Chain
from collections import defaultdict
from tqdm import tqdm
import csv

def check_snapshot_file(chain_id, contract_address, snapshot_type, start_block, end_block=None):
    filename = f'snapshots/{chain_id}/{contract_address}/{snapshot_type}_snapshot_{start_block}'
    if end_block:
        filename += f'_{end_block}'
    filename += '.csv'

    if os.path.isfile(filename):
        print(f"{snapshot_type.capitalize()} snapshot already exists in {filename}")
        return True
    else:
        return False


def read_snapshot_file(chain_id, contract_address, snapshot_type, start_block, end_block=None):
    filename = f'snapshots/{chain_id}/{contract_address}/{snapshot_type}_snapshot_{start_block}'
    if end_block:
        filename += f'_{end_block}'
    filename += '.csv'

    balances = {}
    with open(filename, mode='r', newline='') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header row
        for holder, balance in reader:
            balances[holder] = int(balance)

    return balances

def get_chain_and_contract():
    # Create a session to interact with the database
    Session = init_db()
    session = Session()

    # Query all chains
    chains = session.query(Chain).all()

    # List the chains and prompt for chain selection
    print("Select a chain:")
    for i, chain in enumerate(chains):
        print(f"{i} - {chain.name}")
    chain_idx = int(input("Enter the number for the chain: "))
    chain = chains[chain_idx]

    # List the contracts for the selected chain and prompt for contract selection
    print(f"\nSelect a contract for chain {chain.name}:")
    for i, contract in enumerate(chain.contracts):
        print(f"{i} - {contract.name} ({contract.address})")
    contract_idx = int(input("Enter the number for the contract: "))
    contract = chain.contracts[contract_idx]

    session.close()

    return chain, contract


def write_to_csv(chain_id, contract_address, balances, snapshot_type, start_block, end_block=None):
    filename = f'snapshots/{chain_id}/{contract_address}/{snapshot_type}_snapshot_{start_block}'
    if end_block:
        filename += f'_{end_block}'
    filename += '.csv'

    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Address', 'Balance'])
        for holder, balance in sorted(balances.items(), key=lambda x: x[1], reverse=True):
            writer.writerow([holder, int(balance)])  # Truncating the balance to the nearest integer

    print(f"{snapshot_type.capitalize()} snapshot has been written to {filename}")


def create_snapshot(chain_id, contract_address, block_height, db_session):
    print(f"Creating snapshot for block {block_height}")
    contract = db_session.query(Contract).join(Chain).filter(
        Chain.id == chain_id,
        Contract.address == contract_address
    ).first()

    if not contract:
        print(f"No contract found for chain {chain_id} and address {contract_address}")
        return

    events = db_session.query(Event).filter(
        Event.contract_id == contract.id,
        Event.block_number <= block_height
    ).all()

    balances = defaultdict(int)
    for event in events:
        balances[event.from_address] -= int(event.value)
        balances[event.to_address] += int(event.value)

    return {holder: balance for holder, balance in balances.items()}


def create_single_snapshot(chain_id, contract_address, block_height):
    if check_snapshot_file(chain_id, contract_address, 'single', block_height):
        return read_snapshot_file(chain_id, contract_address, 'single', block_height)
    else:
        Session = init_db()
        session = Session()

        balances = create_snapshot(chain_id, contract_address, block_height, session)

        balances = {holder: balance for holder, balance in balances.items() if balance > 0}

        session.close()

        return {holder: balance for holder, balance in balances.items() if balance > 0}


def create_average_snapshot(chain_id, contract_address, start_block, end_block):
    if check_snapshot_file(chain_id, contract_address,'average', start_block, end_block):
        return read_snapshot_file(chain_id, contract_address,'average', start_block, end_block)
    else:
        Session = init_db()
        session = Session()

        contract = session.query(Contract).join(Chain).filter(
            Chain.id == chain_id,
            Contract.address == contract_address
        ).first()

        if not contract:
            print(f"No contract found for chain {chain_id} and address {contract_address}")
            return

        # Get snapshot for the start block
        balances = create_snapshot(chain_id, contract_address, start_block, session)

        events = session.query(Event).filter(
            Event.contract_id == contract.id,
            Event.block_number > start_block,
            Event.block_number <= end_block
        ).order_by(Event.block_number).all()

        total_balances = defaultdict(int)
        num_blocks = end_block - start_block

        print(f"Processing {len(events)} events...")
        current_block = start_block
        event_idx = 0

        for block_number in tqdm(range(start_block + 1, end_block + 1), desc="Processing blocks"):
            while event_idx < len(events) and events[event_idx].block_number == block_number:
                event = events[event_idx]
                balances[event.from_address] = balances.get(event.from_address, 0) - int(event.value)
                balances[event.to_address] = balances.get(event.to_address, 0) + int(event.value)
                event_idx += 1
            
            # Increment the total balance for this block
            for holder, balance in balances.items():
                total_balances[holder] += balance

        average_balances = {holder: balance / num_blocks for holder, balance in total_balances.items() if balance > 0}

        session.close()

        return {holder: balance / num_blocks for holder, balance in total_balances.items() if balance > 0}


if __name__ == "__main__":
    # Prompt user to select chain and contract
    chain, contract = get_chain_and_contract()

    # Ask user which snapshot they want to create
    snapshot_choice = input("Do you want to create a single snapshot (S) or average snapshot (A)? ").strip().upper()

    if snapshot_choice == 'S':
        block_height = int(input(f"\nEnter the block height for the single snapshot (current: {contract.last_processed_block}): "))
        # Create the single snapshot
        balances = create_single_snapshot(chain_id=chain.id, contract_address=contract.address, block_height=block_height)
        write_to_csv(chain.id, contract.address, 'single', block_height)
    elif snapshot_choice == 'A':
        start_block = int(input(f"\nEnter the start block height for the average snapshot (current: {contract.last_processed_block}): "))
        end_block = int(input(f"Enter the end block height for the average snapshot (current: {contract.last_processed_block}): "))
        if(start_block > contract.last_processed_block):
            start_block = contract.last_processed_block-5000
        if(end_block > contract.last_processed_block):
            end_block = contract.last_processed_block
        balances = create_average_snapshot(chain_id=chain.id, contract_address=contract.address, start_block=start_block, end_block=end_block)
        write_to_csv(balances, 'average', start_block, end_block)
    else:
        print("Invalid choice. Please enter 'S' for single snapshot or 'A' for average snapshot.")
