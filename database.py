from sqlalchemy import create_engine, Column, String, Integer, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

Base = declarative_base()

class Chain(Base):
    __tablename__ = 'chains'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    contracts = relationship('Contract', back_populates='chain')

class Contract(Base):
    __tablename__ = 'contracts'

    id = Column(Integer, primary_key=True)
    chain_id = Column(Integer, ForeignKey('chains.id'), nullable=False)
    name = Column(String)
    address = Column(String)
    last_processed_block = Column(Integer, default=0)

    chain = relationship('Chain', back_populates='contracts')
    events = relationship('Event', back_populates='contract')

class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey('contracts.id'), nullable=False)
    from_address = Column(String)
    to_address = Column(String)
    value = Column(String)
    block_number = Column(Integer)
    transaction_hash = Column(String)

    contract = relationship('Contract', back_populates='events')

def init_db():
    engine = create_engine('sqlite:///events.db')
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)