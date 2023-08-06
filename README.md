# ERC20 Indexer, Snapshot and Airdrop tools

This project includes a tool for indexing ERC20 Transfers, creating snapshots of token balances, and performing airdrops. 

## Setup

### Dependencies

First, setup a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```
Next, install the required dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Edit `config.yml` with the required details for your EVM chains and contracts.

If you want to use the airdrop tool, you'll need to provide some environment variables. Copy `env.example` to `.env` and fill in the details.

## Usage

Remember to activate the venv before calling any of the tools.

#### To run the indexer

```bash
python indexer.py
```

#### To create a snapshot:

```bash
python snapshot.py
```

#### To perform an airdrop:
```bash
python airdrop.py
```

## Running regularly

The airdrop tool is designed to be run regularly, for example by creating a systemd service.

#### Example systemd service file:

```ini
[Unit]
Description=Ethereum Airdrop Service

[Service]
Type=simple
ExecStart=/path/to/venv/bin/python /path/to/airdrop.py
Restart=on-failure
User=your_username
WorkingDirectory=/path/to/project/directory
Environment="PATH=/path/to/venv/bin"
RestartSec=10

[Install]
WantedBy=multi-user.target
```