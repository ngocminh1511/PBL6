"""Neo4j connections with portable, verified TLS for HTTP and CLI clients."""
import ssl


def create_neo4j_driver(uri: str, *, auth, driver_factory=None, **options):
    """Add bundled public CAs to system trust for certificate-verified URIs.

    Build a new context per driver without changing process environment or
    global SSL defaults. Local and explicitly self-signed URI modes retain
    their driver-defined behavior.
    """
    if driver_factory is None:
        from neo4j import GraphDatabase

        driver_factory = GraphDatabase.driver

    scheme, separator, address = uri.partition("://")
    scheme = scheme.lower()
    security_options = {"encrypted", "trusted_certificates", "ssl_context"}
    if scheme in {"neo4j+s", "bolt+s"} and not security_options.intersection(options):
        import certifi

        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        # The driver accepts an explicit SSL context only with unsuffixed
        # schemes. Keep TLS encryption and hostname/CA verification enabled.
        uri = scheme.removesuffix("+s") + separator + address
        options.update(encrypted=True, ssl_context=context)

    return driver_factory(uri, auth=auth, **options)
