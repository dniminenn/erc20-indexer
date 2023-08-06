# ERC20 Indexer, Snapshot and Airdrop tools

This project includes a tool for indexing ERC20 Transfers, creating snapshots of token balances, and performing airdrops.

### Indexer
A tool that retrieves ERC20 transfer events from a variety of EVM-based chains and contracts. The fetched data is kept in an SQLite database for subsequent use or scrutiny.

### Snapshot Tool
A versatile tool that can generate two types of snapshots - single and average. The single snapshot represents the token balances at a specific block height. In contrast, the average snapshot reflects the average state of the integral of token balances across a range of blocks, serving as a temporal representation rather than a single point. This feature eliminates the potential for gaming the snapshot by choosing a particular block.

### Airdrop Tool
A component that uses the snapshots produced by the Snapshot Tool to execute token airdrops. It allows for distribution of tokens to the non-excluded addresses recorded in the snapshot data, creating a convenient method for rewarding token ecosystem participants.

## Setup

### Dependencies

First, clone the repository:

```bash
git clone https://github.com/dniminenn/erc20-indexer
```

Then, setup a virtual environment:

```bash
cd erc20-indexer
python -m venv venv
source venv/bin/activate
```
Next, install the required dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Edit `config.yml` with the required details for your EVM chains and contracts. You may need to set the chunk size according to your node provider's API documentation.

If you want to use the airdrop tool, you'll need to provide some environment variables. Copy `env.example` to `.env` and fill in the details.

## Usage

Remember to activate the venv before calling any of the tools.

#### To run the indexer

```bash
python indexer.py
```

The indexer will populate an sqlite database with the Transfer events of the configured contracts.

#### Create a snapshot

```bash
python snapshot.py
```

The snapshot will be saved in `csv` format under the `snapshots` directory.

#### Perform an airdrop
```bash
python airdrop.py
```

## Running regularly

The airdrop tool is designed to be run regularly, for example by creating a systemd service. Running `airdrop.py` will update the indexes, perform the snapshot and run the airdrop. Failed transactions are saved into a log file and are retried on the next run.

#### Example systemd service file:

/etc/systemd/system/evm-airdrop.service
```ini
[Unit]
Description=Ethereum Airdrop Service

[Service]
Type=oneshot
ExecStart=/path/to/venv/bin/python /path/to/airdrop.py
User=your_username
WorkingDirectory=/path/to/project/directory
Environment="PATH=/path/to/venv/bin"

[Install]
WantedBy=multi-user.target
```

/etc/systemd/system/evm-airdrop.timer
```ini
[Unit]
Description=Run Ethereum Airdrop Service at a random time every three days

[Timer]
OnCalendar=*-*-* 0/3:00:00
RandomizedDelaySec=24h
Persistent=true

[Install]
WantedBy=timers.target
```

Then run the following command to enable the timer
```bash
systemctl enable evm-airdrop.timer
```

Depending on your environment you may opt for a cronjob instead, here's an example crontab entry
```ini
0 0 */3 * * /path/to/venv/bin/python /path/to/airdrop.py >> /path/to/logfile.log 2>&1
```
