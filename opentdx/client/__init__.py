from .standardClient import StandardClient
from .extendedClient import ExtendedClient
from .macStandardClient import MacStandardClient
from .macExtendedClient import MacExtendedClient

QuotationClient = StandardClient
exQuotationClient = ExtendedClient
macQuotationClient = MacStandardClient
macExQuotationClient = MacExtendedClient

__all__ = [
    'StandardClient', 'ExtendedClient', 'MacStandardClient', 'MacExtendedClient',
    'QuotationClient', 'exQuotationClient', 'macQuotationClient', 'macExQuotationClient',
]
