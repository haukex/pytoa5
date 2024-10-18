
PYTHON3BIN = python

.PHONY: all clean installdeps

all:
	$(PYTHON3BIN) -m sphinx -W . html

clean:
	rm -rf html

installdeps:
	$(PYTHON3BIN) -m pur --skip-gt -r requirements.txt
	$(PYTHON3BIN) -m pip install --upgrade --upgrade-strategy=eager -r requirements.txt
