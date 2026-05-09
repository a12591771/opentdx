import pytest

from opentdx.client.standardClient import StandardClient
from opentdx.client.extendedClient import ExtendedClient
from opentdx.client.macStandardClient import MacStandardClient
from opentdx.client.macExtendedClient import MacExtendedClient
from opentdx.tdxClient import TdxClient


@pytest.fixture(scope="session")
def tdx():
    client = TdxClient()
    client.quotation_client = MacStandardClient(True, True)
    client.ex_quotation_client = MacExtendedClient(True, True)
    client.quotation_client.connect().login()
    client.ex_quotation_client.connect().login()
    yield client
    if client.quotation_client.connected:
        client.quotation_client.disconnect()
    if client.ex_quotation_client.connected:
        client.ex_quotation_client.disconnect()


@pytest.fixture(scope="session")
def qc():
    client = StandardClient(True, True)
    client.connect().login()
    yield client
    client.disconnect()


@pytest.fixture(scope="session")
def eqc():
    client = ExtendedClient(True, True)
    client.connect().login()
    yield client
    client.disconnect()


@pytest.fixture(scope="session")
def mqc():
    client = MacStandardClient(True, True)
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture(scope="session")
def meqc():
    client = MacExtendedClient(True, True)
    client.connect()
    yield client
    client.disconnect()


@pytest.fixture(scope="session")
def sp_qc():
    client = MacStandardClient(True, True)
    client.connect().login()
    yield client
    client.disconnect()
