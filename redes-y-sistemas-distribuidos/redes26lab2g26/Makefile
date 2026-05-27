# Pruebas HFTP + Tor (descomprime el kickstart y ejecuta desde esta carpeta).
.PHONY: test-tor test-tor-e2e test
test-tor:
	python3 -m pytest tests/test_tor_hftp.py -v
test-tor-e2e:
	./scripts/tor/test_tor_e2e.sh
test: test-tor
