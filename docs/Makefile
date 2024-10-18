
PYTHON3BIN = python

.PHONY: all clean upd-deps installdeps

all:
	$(PYTHON3BIN) -m sphinx -W . html

clean:
	rm -rf html

upd-deps:
	$(PYTHON3BIN) -m pip install --upgrade --upgrade-strategy=eager pip wheel pur
	$(PYTHON3BIN) -m pur --skip-gt -r requirements.txt

installdeps:
	$(PYTHON3BIN) -m pip install --upgrade --upgrade-strategy=eager -r requirements.txt
